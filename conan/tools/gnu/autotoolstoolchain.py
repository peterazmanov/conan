from conan.tools.build import args_to_string
from conan.tools.apple.apple import apple_min_version_flag, to_apple_arch, get_apple_sdk_name
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, build_type_flags, cppstd_flag, libcxx_flag, \
    build_type_link_flags
from conan.tools.env import Environment
from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conans.errors import ConanException
from conan.tools.microsoft import VCVars, is_msvc


class AutotoolsToolchain:
    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile
        self._namespace = namespace
        build_type = self._conanfile.settings.get_safe("build_type")

        self.configure_args = []
        self.make_args = []
        self.default_configure_install_args = False

        # TODO: compiler.runtime for Visual studio?
        # defines
        self.ndebug = None
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            self.ndebug = "NDEBUG"
        self.gcc_cxx11_abi = self._cxx11_abi_define()
        self.defines = []

        # cxxflags, cflags
        self.cxxflags = []
        self.cflags = []
        self.ldflags = []
        self.libcxx = libcxx_flag(conanfile)
        self.fpic = self._conanfile.options.get_safe("fPIC")

        self.cppstd = cppstd_flag(self._conanfile.settings)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        # TODO: This is also covering compilers like Visual Studio, necessary to test it (&remove?)
        self.build_type_flags = build_type_flags(self._conanfile.settings)
        self.build_type_link_flags = build_type_link_flags(self._conanfile.settings)

        # Cross build
        self._host = None
        self._build = None
        self._target = None

        self.apple_arch_flag = self.apple_isysroot_flag = None

        os_sdk = get_apple_sdk_name(conanfile)
        os_version = conanfile.settings.get_safe("os.version")
        subsystem = conanfile.settings.get_safe("os.subsystem")

        self.apple_min_version_flag = apple_min_version_flag(os_version, os_sdk, subsystem)

        if cross_building(self._conanfile):
            os_host = conanfile.settings.get_safe("os")
            arch_host = conanfile.settings.get_safe("arch")
            os_build = conanfile.settings_build.get_safe('os')
            arch_build = conanfile.settings_build.get_safe('arch')
            compiler = self._conanfile.settings.get_safe("compiler")
            self._host = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            self._build = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

            # Apple Stuff
            if os_build == "Macos":
                # SDK path is mandatory for cross-building
                sdk_path = conanfile.conf["tools.apple:sdk_path"]
                if not sdk_path:
                    raise ConanException("You must provide a valid SDK path for cross-compilation.")
                apple_arch = to_apple_arch(arch_host)
                # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
                self.apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
                # -isysroot makes all includes for your library relative to the build directory
                self.apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

    def _cxx11_abi_define(self):
        # https://gcc.gnu.org/onlinedocs/libstdc++/manual/using_dual_abi.html
        # The default is libstdc++11, only specify the contrary '_GLIBCXX_USE_CXX11_ABI=0'
        settings = self._conanfile.settings
        libcxx = settings.get_safe("compiler.libcxx")
        if not libcxx:
            return

        compiler = settings.get_safe("compiler")
        if compiler in ['clang', 'apple-clang', 'gcc']:
            if libcxx == 'libstdc++':
                return '_GLIBCXX_USE_CXX11_ABI=0'
            elif libcxx == "libstdc++11" and self._conanfile.conf["tools.gnu:define_libcxx11_abi"]:
                return '_GLIBCXX_USE_CXX11_ABI=1'

    def environment(self):
        env = Environment()
        # defines
        if self.ndebug:
            self.defines.append(self.ndebug)
        if self.gcc_cxx11_abi:
            self.defines.append(self.gcc_cxx11_abi)

        if self.libcxx:
            self.cxxflags.append(self.libcxx)

        if self.cppstd:
            self.cxxflags.append(self.cppstd)

        if self.arch_flag:
            self.cxxflags.append(self.arch_flag)
            self.cflags.append(self.arch_flag)
            self.ldflags.append(self.arch_flag)

        if self.build_type_flags:
            self.cxxflags.extend(self.build_type_flags)
            self.cflags.extend(self.build_type_flags)

        if self.build_type_link_flags:
            self.ldflags.extend(self.build_type_link_flags)

        if self.fpic:
            self.cxxflags.append("-fPIC")
            self.cflags.append("-fPIC")

        if is_msvc(self._conanfile):
            env.define("CXX", "cl")
            env.define("CC", "cl")

        # FIXME: Previously these flags where checked if already present at env 'CFLAGS', 'CXXFLAGS'
        #        and 'self.cxxflags', 'self.cflags' before adding them
        for f in list(filter(bool, [self.apple_isysroot_flag,
                                    self.apple_arch_flag,
                                    self.apple_min_version_flag])):
            self.cxxflags.append(f)
            self.cflags.append(f)
            self.ldflags.append(f)

        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        return env

    def vars(self):
        return self.environment().vars(self._conanfile, scope="build")

    def generate(self, env=None, scope="build"):
        env = env or self.environment()
        env = env.vars(self._conanfile, scope=scope)
        env.save_script("conanautotoolstoolchain")
        self.generate_args()
        VCVars(self._conanfile).generate(scope=scope)

    def generate_args(self):
        configure_args = []
        configure_args.extend(self.configure_args)

        if self.default_configure_install_args:
            # If someone want arguments but not the defaults can pass them in args manually
            configure_args.extend(
                    ["--prefix=%s" % self._conanfile.package_folder.replace("\\", "/"),
                     "--bindir=${prefix}/bin",
                     "--sbindir=${prefix}/bin",
                     "--libdir=${prefix}/lib",
                     "--includedir=${prefix}/include",
                     "--oldincludedir=${prefix}/include",
                     "--datarootdir=${prefix}/share"])
        user_args_str = args_to_string(self.configure_args)
        for flag, var in (("host", self._host), ("build", self._build), ("target", self._target)):
            if var and flag not in user_args_str:
                configure_args.append('--{}={}'.format(flag, var))

        args = {"configure_args": args_to_string(configure_args),
                "make_args":  args_to_string(self.make_args)}

        save_toolchain_args(args, namespace=self._namespace)
