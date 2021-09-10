from conans.client.tools import no_op
from conans.errors import conanfile_exception_formatter
from conans.model.pkg_type import PackageType
from conans.model.requires import BuildRequirements, TestRequirements
from conans.util.conan_v2_mode import conan_v2_error


def run_configure_method(conanfile, down_options, down_ref, ref):
    """ Run all the config-related functions for the given conanfile object """

    # Avoid extra time manipulating the sys.path for python
    with no_op():  # TODO: Remove this in a later refactor
        if hasattr(conanfile, "config"):
            conan_v2_error("config() has been deprecated. Use config_options() and configure()")
            with conanfile_exception_formatter(str(conanfile), "config"):
                conanfile.config()

        with conanfile_exception_formatter(str(conanfile), "config_options"):
            conanfile.config_options()

        conanfile.options.propagate_upstream(down_options, down_ref, ref)

        if hasattr(conanfile, "config"):
            with conanfile_exception_formatter(str(conanfile), "config"):
                conanfile.config()

        with conanfile_exception_formatter(str(conanfile), "configure"):
            conanfile.configure()

        PackageType.compute_package_type(conanfile)

        if hasattr(conanfile, "requirements"):
            with conanfile_exception_formatter(str(conanfile), "requirements"):
                conanfile.requirements()

        # TODO: Maybe this could be integrated in one single requirements() method
        if hasattr(conanfile, "build_requirements"):
            with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                conanfile.build_requires = BuildRequirements(conanfile.requires)
                conanfile.test_requires = TestRequirements(conanfile.requires)
                conanfile.build_requirements()

        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(str(conanfile), "layout"):
                conanfile.layout()
