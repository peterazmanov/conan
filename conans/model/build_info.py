import os
from collections import OrderedDict
from copy import copy

from conans.errors import ConanException
from conans.util.conan_v2_mode import conan_v2_error

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""
DEFAULT_FRAMEWORK = "Frameworks"

COMPONENT_SCOPE = "::"


class DefaultOrderedDict(OrderedDict):

    def __init__(self, factory):
        self.factory = factory
        super(DefaultOrderedDict, self).__init__()

    def __getitem__(self, key):
        if key not in self.keys():
            super(DefaultOrderedDict, self).__setitem__(key, self.factory())
            super(DefaultOrderedDict, self).__getitem__(key).name = key
        return super(DefaultOrderedDict, self).__getitem__(key)

    def __copy__(self):
        the_copy = DefaultOrderedDict(self.factory)
        for key, value in super(DefaultOrderedDict, self).items():
            the_copy[key] = value
        return the_copy


class BuildModulesDict(dict):
    """
    A dictionary with append and extend for cmake build modules to keep it backwards compatible
    with the list interface
    """

    def __getitem__(self, key):
        if key not in self.keys():
            super(BuildModulesDict, self).__setitem__(key, list())
        return super(BuildModulesDict, self).__getitem__(key)

    def _append(self, item):
        if item.endswith(".cmake"):
            self["cmake"].append(item)
            self["cmake_multi"].append(item)
            self["cmake_find_package"].append(item)
            self["cmake_find_package_multi"].append(item)

    def append(self, item):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].append(\"{item}\")' "
                       'instead'.format(item=item))
        self._append(item)

    def extend(self, items):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].extend({items})' "
                       "instead".format(items=items))
        for item in items:
            self._append(item)

    @classmethod
    def from_list(cls, build_modules):
        the_dict = BuildModulesDict()
        the_dict.extend(build_modules)
        return the_dict


def dict_to_abs_paths(the_dict, rootpath):
    new_dict = {}
    for generator, values in the_dict.items():
        new_dict[generator] = [os.path.join(rootpath, p) if not os.path.isabs(p) else p
                               for p in values]
    return new_dict


def merge_lists(seq1, seq2):
    return seq1 + [s for s in seq2 if s not in seq1]


def merge_dicts(d1, d2):
    def merge_lists(seq1, seq2):
        return [s for s in seq1 if s not in seq2] + seq2

    result = d1.copy()
    for k, v in d2.items():
        if k not in d1.keys():
            result[k] = v
        else:
            result[k] = merge_lists(d1[k], d2[k])
    return result


class _CppInfo(object):
    """ Object that stores all the necessary information to build in C/C++.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """

    def __init__(self):
        self._name = None
        self.names = {}
        self.system_libs = []  # Ordered list of system libraries
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.frameworks = []  # Macos .framework
        self.frameworkdirs = []
        self.rootpaths = []
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.build_modules = BuildModulesDict()  # FIXME: This should be just a plain dict
        self.filenames = {}  # name of filename to create for various generators
        self._rootpath = ""
        self.sysroot = ""
        self.requires = []
        self._build_modules_paths = None
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._framework_paths = None
        self.version = None  # Version of the conan package
        self.description = None  # Description of the conan package
        # By default we don't filter empty, because we want to filter ONLY when the final cppinfo
        # from package is full of files but before that we will play with the build and source layout
        # and cppinfo and it mess a lot
        self.filter_empty = False

    @property
    def rootpath(self):
        return self._rootpath

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self._rootpath, p)
                     if not os.path.isabs(p) else p for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def build_modules_paths(self):
        if self._build_modules_paths is None:
            if isinstance(self.build_modules, list):  # FIXME: This should be just a plain dict
                conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"] = "
                               "{the_list}' instead".format(the_list=self.build_modules))
                self.build_modules = BuildModulesDict.from_list(self.build_modules)
            tmp = dict_to_abs_paths(BuildModulesDict(self.build_modules), self._rootpath)
            self._build_modules_paths = tmp
        return self._build_modules_paths

    @property
    def include_paths(self):
        if self._include_paths is None:
            self._include_paths = self._filter_paths(self.includedirs)
        return self._include_paths

    @property
    def lib_paths(self):
        if self._lib_paths is None:
            self._lib_paths = self._filter_paths(self.libdirs)
        return self._lib_paths

    @property
    def src_paths(self):
        if self._src_paths is None:
            self._src_paths = self._filter_paths(self.srcdirs)
        return self._src_paths

    @property
    def bin_paths(self):
        if self._bin_paths is None:
            self._bin_paths = self._filter_paths(self.bindirs)
        return self._bin_paths

    @property
    def build_paths(self):
        if self._build_paths is None:
            self._build_paths = self._filter_paths(self.builddirs)
        return self._build_paths

    @property
    def res_paths(self):
        if self._res_paths is None:
            self._res_paths = self._filter_paths(self.resdirs)
        return self._res_paths

    @property
    def framework_paths(self):
        if self._framework_paths is None:
            self._framework_paths = self._filter_paths(self.frameworkdirs)
        return self._framework_paths

    @property
    def name(self):
        conan_v2_error("Use 'get_name(generator)' instead")
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def get_name(self, generator):
        return self.names.get(generator, self._name)

    def get_filename(self, generator):
        result = self.filenames.get(generator)
        if result:
            return result
        return self.get_name(generator)

    # Compatibility for 'cppflags' (old style property to allow decoration)
    def get_cppflags(self):
        conan_v2_error("'cpp_info.cppflags' is deprecated, use 'cxxflags' instead")
        return self.cxxflags

    def set_cppflags(self, value):
        conan_v2_error("'cpp_info.cppflags' is deprecated, use 'cxxflags' instead")
        self.cxxflags = value

    cppflags = property(get_cppflags, set_cppflags)

    def merge(self, other, rootpath):
        """Accumulate in a cppinfo object another one containing entries of a subdirectory,
        for example the editable root containing two cppinfos, the source one and the build one"""
        relpath = os.path.relpath(other._rootpath, rootpath)

        def _merge_dir_list(seq1, seq2):
            news = ["%s/%s" % (relpath, rs) if relpath != "." else rs for rs in seq2]
            seq1.extend([n for n in news if n not in seq1])

        def _merge_list(seq1, seq2):
            seq1.extend([rs for rs in seq2 if rs not in seq1])

        def _merge_build_modules_dict(seq1, seq2):
            for k, v in seq2.items():
                seq1[k] = v if k not in seq1 else _merge_list(seq1[k], seq2[k])

        _merge_dir_list(self.includedirs, other.includedirs)
        _merge_dir_list(self.libdirs, other.libdirs)
        _merge_dir_list(self.bindirs, other.bindirs)
        _merge_dir_list(self.resdirs, other.resdirs)
        _merge_dir_list(self.builddirs, other.builddirs)
        _merge_dir_list(self.frameworkdirs, other.frameworkdirs)
        _merge_list(self.libs, other.libs)
        _merge_list(self.defines, other.defines)
        _merge_list(self.cflags, other.cflags)
        _merge_list(self.cxxflags, other.cxxflags)
        _merge_list(self.sharedlinkflags, other.sharedlinkflags)
        _merge_list(self.exelinkflags, other.exelinkflags)
        _merge_list(self.system_libs, other.system_libs)
        _merge_list(self.rootpaths, other.rootpaths)
        self.filenames.update(other.filenames)
        _merge_list(self.requires, other.requires)
        _merge_build_modules_dict(self.build_modules, other.build_modules)


class Component(_CppInfo):

    def __init__(self, rootpath, version, default_values, filter_empty):
        super(Component, self).__init__()

        self._rootpath = rootpath

        if default_values.includedir is not None:
            self.includedirs.append(default_values.includedir)
        if default_values.libdir is not None:
            self.libdirs.append(default_values.libdir)
        if default_values.bindir is not None:
            self.bindirs.append(default_values.bindir)
        if default_values.resdir is not None:
            self.resdirs.append(default_values.resdir)
        if default_values.builddir is not None:
            self.builddirs.append(default_values.builddir)
        if default_values.frameworkdir is not None:
            self.frameworkdirs.append(default_values.frameworkdir)
        self.requires = []
        self.version = version
        self.filter_empty = filter_empty


class CppInfoDefaultValues(object):

    def __init__(self, includedir=None, libdir=None, bindir=None, resdir=None, builddir=None,
                 frameworkdir=None):

        self.includedir = includedir
        self.libdir = libdir
        self.bindir = bindir
        self.resdir = resdir
        self.builddir = builddir
        self.frameworkdir = frameworkdir


class CppInfo(_CppInfo):
    """ Build Information declared to be used by the CONSUMERS of a
    conans. That means that consumers must use this flags and configs i order
    to build properly.
    Defined in user CONANFILE, directories are relative at user definition time
    """

    def __init__(self, ref_name, root_folder, default_values=None):
        super(CppInfo, self).__init__()
        self._ref_name = ref_name
        self._name = ref_name
        self._rootpath = root_folder  # the full path of the package in which the conans is found
        self._default_values = default_values or CppInfoDefaultValues(DEFAULT_INCLUDE, DEFAULT_LIB,
                                                                      DEFAULT_BIN, DEFAULT_RES,
                                                                      DEFAULT_BUILD,
                                                                      DEFAULT_FRAMEWORK)
        if self._default_values.includedir is not None:
            self.includedirs.append(self._default_values.includedir)
        if self._default_values.libdir is not None:
            self.libdirs.append(self._default_values.libdir)
        if self._default_values.bindir is not None:
            self.bindirs.append(self._default_values.bindir)
        if self._default_values.resdir is not None:
            self.resdirs.append(self._default_values.resdir)
        if self._default_values.builddir is not None:
            self.builddirs.append(self._default_values.builddir)
        if self._default_values.frameworkdir is not None:
            self.frameworkdirs.append(self._default_values.frameworkdir)

        self.components = DefaultOrderedDict(lambda: Component(self._rootpath,
                                                               self.version, self._default_values,
                                                               self.filter_empty))
        # public_deps is needed to accumulate list of deps for cmake targets
        self.public_deps = []
        self._configs = {}

    @property
    def rootpath(self):
        return self._rootpath

    @rootpath.setter
    def rootpath(self, path):
        self._rootpath = path
        for c in self.components.values():
            c._rootpath = path
        for c in self._configs.values():
            c._rootpath = path

    def merge(self, other, rootpath=None):
        """ Used to aggregate build info objects when we have build and source declared
        in the recipe layout and it is consumed as an editable package"""
        super().merge(other, rootpath or self.rootpath)

        for k, v in other.components.items():
            # Use the rootpath from this general build info, not from the component
            self.components[k].merge(v, self.rootpath)

    def __str__(self):
        return self._ref_name

    def get_name(self, generator):
        name = super(CppInfo, self).get_name(generator)

        # Legacy logic for pkg_config generator
        from conans.client.generators.pkg_config import PkgConfigGenerator
        if generator == PkgConfigGenerator.name:
            fallback = self._name.lower() if self._name != self._ref_name else self._ref_name
            if PkgConfigGenerator.name not in self.names and self._name != self._name.lower():
                conan_v2_error("Generated file and name for {gen} generator will change in"
                               " Conan v2 to '{name}'. Use 'self.cpp_info.names[\"{gen}\"]"
                               " = \"{fallback}\"' in your recipe to continue using current name."
                               .format(gen=PkgConfigGenerator.name, name=name, fallback=fallback))
            name = self.names.get(generator, fallback)
        return name

    @property
    def configs(self):
        return self._configs

    def __getattr__(self, config):
        def _get_cpp_info():
            result = _CppInfo()
            result.filter_empty = self.filter_empty
            result._rootpath = self._rootpath
            result.sysroot = self.sysroot
            result.includedirs.append(self._default_values.includedir)
            result.libdirs.append(self._default_values.libdir)
            result.bindirs.append(self._default_values.bindir)
            result.resdirs.append(self._default_values.resdir)
            result.builddirs.append(self._default_values.builddir)
            result.frameworkdirs.append(self._default_values.frameworkdir)
            return result

        return self._configs.setdefault(config, _get_cpp_info())

    def _raise_incorrect_components_definition(self, package_name, package_requires):
        if not self.components and not self.requires:
            return

        # Raise if mixing components
        if self.components and \
            (self.includedirs != [self._default_values.includedir] or
             self.libdirs != [self._default_values.libdir] or
             self.bindirs != [self._default_values.bindir] or
             self.resdirs != [self._default_values.resdir] or
             self.builddirs != [self._default_values.builddir] or
             self.frameworkdirs != [self._default_values.frameworkdir] or
             self.libs or
             self.system_libs or
             self.frameworks or
             self.defines or
             self.cflags or
             self.cxxflags or
             self.sharedlinkflags or
             self.exelinkflags or
             self.build_modules or
             self.requires):
            raise ConanException("self.cpp_info.components cannot be used with self.cpp_info "
                                 "global values at the same time")
        if self._configs:
            raise ConanException("self.cpp_info.components cannot be used with self.cpp_info configs"
                                 " (release/debug/...) at the same time")

        pkg_requires = [require.ref.name for require in package_requires.values()]

        def _check_components_requires_instersection(comp_requires):
            reqs = [it.split(COMPONENT_SCOPE)[0] for it in comp_requires if COMPONENT_SCOPE in it]
            # Raise on components requires without package requires
            for pkg_require in pkg_requires:
                if package_requires[pkg_require].private or package_requires[pkg_require].override:
                    # Not standard requires, skip
                    continue
                if pkg_require not in reqs:
                    raise ConanException("Package require '%s' not used in components requires"
                                         % pkg_require)
            # Raise on components requires requiring inexistent package requires
            for comp_require in reqs:
                reason = None
                if comp_require not in pkg_requires:
                    reason = "not defined as a recipe requirement"
                elif package_requires[comp_require].private and package_requires[
                    comp_require].override:
                    reason = "it was defined as an overridden private recipe requirement"
                elif package_requires[comp_require].private:
                    reason = "it was defined as a private recipe requirement"
                elif package_requires[comp_require].override:
                    reason = "it was defined as an overridden recipe requirement"

                if reason is not None:
                    raise ConanException("Package require '%s' declared in components requires "
                                         "but %s" % (comp_require, reason))

        if self.components:
            # Raise on component name
            for comp_name, comp in self.components.items():
                if comp_name == package_name:
                    raise ConanException(
                        "Component name cannot be the same as the package name: '%s'"
                        % comp_name)

            # check that requires are used in components and check that components exists in requires
            requires_from_components = set()
            for comp_name, comp in self.components.items():
                requires_from_components.update(comp.requires)
            _check_components_requires_instersection(requires_from_components)
        else:
            _check_components_requires_instersection(self.requires)


class _BaseDepsCppInfo(_CppInfo):
    def __init__(self):
        super(_BaseDepsCppInfo, self).__init__()

    def update(self, dep_cpp_info):
        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        self.system_libs = merge_lists(self.system_libs, dep_cpp_info.system_libs)
        self.includedirs = merge_lists(self.includedirs, dep_cpp_info.include_paths)
        self.srcdirs = merge_lists(self.srcdirs, dep_cpp_info.src_paths)
        self.libdirs = merge_lists(self.libdirs, dep_cpp_info.lib_paths)
        self.bindirs = merge_lists(self.bindirs, dep_cpp_info.bin_paths)
        self.resdirs = merge_lists(self.resdirs, dep_cpp_info.res_paths)
        self.builddirs = merge_lists(self.builddirs, dep_cpp_info.build_paths)
        self.frameworkdirs = merge_lists(self.frameworkdirs, dep_cpp_info.framework_paths)
        self.libs = merge_lists(self.libs, dep_cpp_info.libs)
        self.frameworks = merge_lists(self.frameworks, dep_cpp_info.frameworks)
        self.build_modules = merge_dicts(self.build_modules, dep_cpp_info.build_modules_paths)
        self.requires = merge_lists(self.requires, dep_cpp_info.requires)
        self.rootpaths.append(dep_cpp_info.rootpath)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cxxflags = merge_lists(dep_cpp_info.cxxflags, self.cxxflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)

        if not self.sysroot:
            self.sysroot = dep_cpp_info.sysroot

    @property
    def build_modules_paths(self):
        return self.build_modules

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def src_paths(self):
        return self.srcdirs

    @property
    def bin_paths(self):
        return self.bindirs

    @property
    def build_paths(self):
        return self.builddirs

    @property
    def res_paths(self):
        return self.resdirs

    @property
    def framework_paths(self):
        return self.frameworkdirs


class DepCppInfo(object):

    def __init__(self, cpp_info):
        self._cpp_info = cpp_info
        self._libs = None
        self._system_libs = None
        self._frameworks = None
        self._defines = None
        self._cxxflags = None
        self._cflags = None
        self._sharedlinkflags = None
        self._exelinkflags = None
        self._requires = None

        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._framework_paths = None
        self._build_modules_paths = None
        self._sorted_components = None
        self._check_component_requires()

    def __str__(self):
        return str(self._cpp_info)

    def __getattr__(self, item):
        try:
            attr = self._cpp_info.__getattribute__(item)
        except AttributeError:  # item is not defined, get config (CppInfo)
            attr = self._cpp_info.__getattr__(item)
        return attr

    def _aggregated_values(self, item, agg_func=merge_lists):
        values = getattr(self, "_%s" % item)
        if values is not None:
            return values
        values = getattr(self._cpp_info, item)
        if self._cpp_info.components:
            for component in self._get_sorted_components().values():
                values = agg_func(values, getattr(component, item))
        setattr(self, "_%s" % item, values)
        return values

    @staticmethod
    def _filter_component_requires(requires):
        return [r for r in requires if COMPONENT_SCOPE not in r]

    def _check_component_requires(self):
        for comp_name, comp in self._cpp_info.components.items():
            missing_deps = [require for require in self._filter_component_requires(comp.requires)
                            if require not in self._cpp_info.components]
            if missing_deps:
                raise ConanException("Component '%s' required components not found in this package: "
                                     "%s" % (comp_name, ", ".join("'%s'" % d for d in missing_deps)))
            bad_requires = [r for r in comp.requires if r.startswith(COMPONENT_SCOPE)]
            if bad_requires:
                msg = "Leading character '%s' not allowed in %s requires: %s. Omit it to require " \
                      "components inside the same package." \
                      % (COMPONENT_SCOPE, comp_name, bad_requires)
                raise ConanException(msg)

    def _get_sorted_components(self):
        """
        Sort Components from most dependent one first to the less dependent one last
        :return: List of sorted components
        """
        if not self._sorted_components:
            if any([[require for require in self._filter_component_requires(comp.requires)]
                    for comp in self._cpp_info.components.values()]):
                ordered = OrderedDict()
                components = copy(self._cpp_info.components)
                while len(ordered) != len(self._cpp_info.components):
                    # Search next element to be processed
                    for comp_name, comp in components.items():
                        # Check if component is not required and can be added to ordered
                        if comp_name not in [require for dep in components.values() for require in
                                             self._filter_component_requires(dep.requires)]:
                            ordered[comp_name] = comp
                            del components[comp_name]
                            break
                    else:
                        raise ConanException("There is a dependency loop in "
                                             "'self.cpp_info.components' requires")
                self._sorted_components = ordered
            else:  # If components do not have requirements, keep them in the same order
                self._sorted_components = self._cpp_info.components
        return self._sorted_components

    @property
    def build_modules_paths(self):
        return self._aggregated_values("build_modules_paths", agg_func=merge_dicts)

    @property
    def include_paths(self):
        return self._aggregated_values("include_paths")

    @property
    def lib_paths(self):
        return self._aggregated_values("lib_paths")

    @property
    def src_paths(self):
        return self._aggregated_values("src_paths")

    @property
    def bin_paths(self):
        return self._aggregated_values("bin_paths")

    @property
    def build_paths(self):
        return self._aggregated_values("build_paths")

    @property
    def res_paths(self):
        return self._aggregated_values("res_paths")

    @property
    def framework_paths(self):
        return self._aggregated_values("framework_paths")

    @property
    def libs(self):
        return self._aggregated_values("libs")

    @property
    def system_libs(self):
        return self._aggregated_values("system_libs")

    @property
    def frameworks(self):
        return self._aggregated_values("frameworks")

    @property
    def defines(self):
        return self._aggregated_values("defines")

    @property
    def cxxflags(self):
        return self._aggregated_values("cxxflags")

    @property
    def cflags(self):
        return self._aggregated_values("cflags")

    @property
    def sharedlinkflags(self):
        return self._aggregated_values("sharedlinkflags")

    @property
    def exelinkflags(self):
        return self._aggregated_values("exelinkflags")

    @property
    def requires(self):
        return self._aggregated_values("requires")


class DepsCppInfo(_BaseDepsCppInfo):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """

    def __init__(self):
        super(DepsCppInfo, self).__init__()
        self._dependencies = OrderedDict()
        self._configs = {}

    def __getattr__(self, config):
        return self._configs.setdefault(config, _BaseDepsCppInfo())

    @property
    def configs(self):
        return self._configs

    @property
    def dependencies(self):
        return self._dependencies.items()

    @property
    def deps(self):
        return self._dependencies.keys()

    def __getitem__(self, item):
        return self._dependencies[item]

    def add(self, pkg_name, cpp_info):
        assert pkg_name == str(cpp_info), "'{}' != '{}'".format(pkg_name, cpp_info)
        assert isinstance(cpp_info, (CppInfo, DepCppInfo))
        self._dependencies[pkg_name] = cpp_info
        super(DepsCppInfo, self).update(cpp_info)
        for config, cpp_info in cpp_info.configs.items():
            self._configs.setdefault(config, _BaseDepsCppInfo()).update(cpp_info)
