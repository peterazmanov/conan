import os
import textwrap
import unittest
from collections import Counter

from mock import Mock

from conans.client.cache.cache import ClientCache
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import PyRequireLoader
from conans.client.graph.range_resolver import RangeResolver
from conans.client.installer import BinaryInstaller
from conans.client.loader import ConanFileLoader
from conans.model.manifest import FileTreeManifest
from conans.model.options import Options
from conans.model.profile import Profile
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import GenConanfile
from conans.util.dates import revision_timestamp_now
from conans.util.files import save


class MockRemoteManager(object):
    def __init__(self, packages=None):
        self.packages = packages or []
        self.count = Counter()

    def search_recipes(self, remote, pattern, ignorecase):  # @UnusedVariable
        self.count[pattern] += 1
        return self.packages


class GraphManagerTest(unittest.TestCase):

    def setUp(self):
        cache_folder = temp_folder()
        cache = ClientCache(cache_folder)
        save(cache.default_profile_path, "")
        save(cache.settings_path, "os: [Windows, Linux]")
        self.cache = cache

    def _get_app(self):
        self.remote_manager = MockRemoteManager()
        cache = self.cache
        app = Mock()
        app.cache = cache
        app.remote_manager = self.remote_manager
        app.enabled_remotes = []
        app.selected_remotes = []
        app.check_updates = False
        app.update = False
        app.range_resolver = RangeResolver(app)
        app.proxy = ConanProxy(app)
        pyreq_loader = PyRequireLoader(app.proxy, app.range_resolver)
        app.loader = ConanFileLoader(pyreq_loader=pyreq_loader)
        app.binaries_analyzer = GraphBinariesAnalyzer(app)
        app.graph_manager = GraphManager(app)
        app.hook_manager = Mock()
        return app

    def recipe_cache(self, reference, requires=None, option_shared=None):
        ref = RecipeReference.loads(reference)
        conanfile = GenConanfile()
        if requires:
            for r in requires:
                conanfile.with_require(r)
        if option_shared is not None:
            conanfile.with_option("shared", [True, False])
            conanfile.with_default_option("shared", option_shared)

        self._put_in_cache(ref, conanfile)

    def recipe_conanfile(self, reference, conanfile):
        ref = RecipeReference.loads(reference)
        self._put_in_cache(ref, conanfile)

    def _put_in_cache(self, ref, conanfile):
        ref = RecipeReference.loads("{}#123".format(ref))
        ref.timestamp = revision_timestamp_now()
        layout = self.cache.get_or_create_ref_layout(ref)
        save(layout.conanfile(), str(conanfile))
        manifest = FileTreeManifest.create(layout.export())
        manifest.save(layout.export())

    def _cache_recipe(self, ref, test_conanfile, revision=None):
        # FIXME: This seems duplicated
        if not isinstance(ref, RecipeReference):
            ref = RecipeReference.loads(ref)
        ref = RecipeReference.loads(repr(ref) + "#{}".format(revision or 123))  # FIXME: Make access
        ref.timestamp = revision_timestamp_now()
        recipe_layout = self.cache.get_or_create_ref_layout(ref)
        save(recipe_layout.conanfile(), str(test_conanfile))
        manifest = FileTreeManifest.create(recipe_layout.export())
        manifest.save(recipe_layout.export())

    def alias_cache(self, alias, target):
        ref = RecipeReference.loads(alias)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Alias(ConanFile):
                alias = "%s"
            """ % target)
        self._put_in_cache(ref, conanfile)

    @staticmethod
    def recipe_consumer(reference=None, requires=None, build_requires=None, tool_requires=None):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        conanfile = GenConanfile()
        if reference:
            ref = RecipeReference.loads(reference)
            conanfile.with_name(ref.name).with_version(ref.version)
        if requires:
            for r in requires:
                conanfile.with_require(r)
        if build_requires:
            for r in build_requires:
                conanfile.with_build_requires(r)
        if tool_requires:
            for r in tool_requires:
                conanfile.with_tool_requires(r)
        save(path, str(conanfile))
        return path

    @staticmethod
    def consumer_conanfile(conanfile):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        save(path, str(conanfile))
        return path

    def build_graph(self, content, profile_build_requires=None, ref=None, create_ref=None,
                    install=True, options_build=None):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        save(path, str(content))
        return self.build_consumer(path, profile_build_requires, ref, create_ref, install,
                                   options_build=options_build)

    def build_consumer(self, path, profile_build_requires=None, ref=None, create_ref=None,
                       install=True, options_build=None):
        profile_host = Profile()
        profile_host.settings["os"] = "Linux"
        profile_build = Profile()
        profile_build.settings["os"] = "Windows"
        if profile_build_requires:
            profile_host.tool_requires = profile_build_requires
        if options_build:
            profile_build.options = Options(options_values=options_build)
        profile_host.process_settings(self.cache)
        profile_build.process_settings(self.cache)
        build_mode = []  # Means build all
        ref = ref or RecipeReference(None, None, None, None)
        app = self._get_app()

        deps_graph = app.graph_manager.load_graph(path, create_ref, profile_host, profile_build,
                                                  None, ref, build_mode)
        if install:
            deps_graph.report_graph_error()
            binary_installer = BinaryInstaller(app)
            
            binary_installer.install(deps_graph)

        return deps_graph

    def _check_node(self, node, ref, deps=None, dependents=None, settings=None, options=None):
        dependents = dependents or []
        deps = deps or []

        conanfile = node.conanfile
        ref = RecipeReference.loads(str(ref))
        self.assertEqual(node.ref, ref)
        if conanfile:
            self.assertEqual(conanfile.name, ref.name)

        self.assertEqual(len(node.dependencies), len(deps))
        for d in node.neighbors():
            assert d in deps

        dependants = node.inverse_neighbors()
        self.assertEqual(len(dependants), len(dependents))
        for d in dependents:
            self.assertIn(d, dependants)

        if settings is not None:
            for k, v in settings.items():
                assert conanfile.settings.get_safe(k) == v

        if options is not None:
            for k, v in options.items():
                assert conanfile.options.get_safe(k) == v
