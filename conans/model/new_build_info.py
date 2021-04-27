import copy
import os
from collections import OrderedDict

from conans.model.build_info import DefaultOrderedDict

_DIRS_VAR_NAMES = ["includedirs", "srcdirs", "libdirs", "resdirs", "bindirs", "builddirs",
                   "frameworkdirs"]
_FIELD_VAR_NAMES = ["system_libs", "frameworks", "libs", "defines", "cflags", "cxxflags",
                    "sharedlinkflags", "exelinkflags"]


class _NewComponent(object):

    def __init__(self, none_values):

        # ###### PROPERTIES
        self._generator_properties = None if none_values else {}

        # ###### DIRECTORIES
        self.includedirs = None if none_values else []  # Ordered list of include paths
        self.srcdirs = None if none_values else []  # Ordered list of source paths
        self.libdirs = None if none_values else []  # Directories to find libraries
        self.resdirs = None if none_values else []  # Directories to find resources, data, etc
        self.bindirs = None if none_values else []  # Directories to find executables and shared libs
        self.builddirs = None if none_values else []
        self.frameworkdirs = None if none_values else []

        # ##### FIELDS
        self.system_libs = None if none_values else []  # Ordered list of system libraries
        self.frameworks = None if none_values else []  # Macos .framework
        self.libs = None if none_values else []  # The libs to link against
        self.defines = None if none_values else []  # preprocessor definitions
        self.cflags = None if none_values else []  # pure C flags
        self.cxxflags = None if none_values else []  # C++ compilation flags
        self.sharedlinkflags = None if none_values else []  # linker flags
        self.exelinkflags = None if none_values else []  # linker flags

        self.sysroot = None if none_values else ""
        self.requires = None if none_values else []

    @property
    def required_component_names(self):
        """ Names of the required components of the same package (not scoped with ::)"""
        if not self.requires:
            return []
        return [r for r in self.requires if "::" not in r]

    def set_property(self, property_name, value, generator=None):
        if not self._generator_properties:
            self._generator_properties = {}
        self._generator_properties.setdefault(generator, {})[property_name] = value

    def get_property(self, property_name, generator=None):
        if not self._generator_properties:
            return None
        if generator:
            try:
                return self._generator_properties[generator][property_name]
            except KeyError:
                pass
        try:
            return self._generator_properties[None][property_name]
        except KeyError:
            pass


class NewCppInfo(object):

    def __init__(self, none_values=False):
        super(NewCppInfo, self).__init__()
        self.components = DefaultOrderedDict(lambda: _NewComponent(none_values))
        # Main package is a component with None key
        self.components[None] = _NewComponent(none_values)

    def __getattr__(self, attr):
        return getattr(self.components[None], attr)

    def __setattr__(self, attr, value):
        if attr in ["components"]:
            super(NewCppInfo, self).__setattr__(attr, value)
        else:
            setattr(self.components[None], attr, value)

    @property
    def has_components(self):
        return len(self.components) > 1

    @property
    def component_names(self):
        return filter(None, self.components.keys())

    @staticmethod
    def from_old_cppinfo(old):
        ret = NewCppInfo()
        ret.merge(old)
        return ret

    def merge(self, other):
        def merge_list(o, d):
            for e in o:
                if e not in d:
                    d.append(e)

        for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            if not getattr(other, varname):
                continue
            if getattr(self, varname) is None:
                setattr(self, varname, [])
            merge_list(getattr(other, varname), getattr(self, varname))

        if other._generator_properties:
            if not self._generator_properties:
                self._generator_properties = {}
            self._generator_properties.update(other._generator_properties)

        # COMPONENTS
        for cname, c in other.components.items():
            if cname is None:
                continue
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                if not getattr(c, varname):
                    continue
                if getattr(self.components[cname], varname) is None:
                    setattr(self.components[cname], varname, [])
                merge_list(getattr(c, varname), getattr(self.components[cname], varname))
            if c.requires:
                if self.components[cname].requires is None:
                    self.components[cname].requires = []
                merge_list(c.requires, self.components[cname].requires)

            if c._generator_properties:
                if self.components[cname]._generator_properties is None:
                    self.components[cname]._generator_properties = {}
                self.components[cname]._generator_properties.update(c._generator_properties)

    def set_relative_base_folder(self, folder):
        """Prepend the folder to all the directories"""
        for cname, c in self.components.items():
            for varname in _DIRS_VAR_NAMES:
                new_list = []
                origin = getattr(self.components[cname], varname)
                if origin is not None:
                    for el in origin:
                        new_list.append(os.path.join(folder, el))
                    setattr(self.components[cname], varname, new_list)

    def get_sorted_components(self):
        """Order the components taking into account if they depend on another component in the
        same package (not scoped with ::). First less dependant
        return:  {component_name: component}
        """
        processed = []  # Names of the components ordered
        # FIXME: Cache the sort
        while (len(self.components) - 1) > len(processed):
            for name, c in self.components.items():
                if name is None:
                    continue
                req_processed = [n for n in c.required_component_names if n not in processed]
                if not req_processed and name not in processed:
                    processed.append(name)

        return OrderedDict([(cname,  self.components[cname]) for cname in processed])

    def aggregate_components(self):
        """Aggregates all the components as global values"""
        if self.has_components:
            components = self.get_sorted_components()
            cnames = list(components.keys())
            cnames.reverse()  # More dependant first

            # Clean global values
            for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                setattr(self.components[None], n, [])

            for name in cnames:
                component = components[name]
                for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                    dest = getattr(self.components[None], n)
                    dest += [i for i in getattr(component, n) if i not in dest]
                self.components[None].requires.extend(component.requires)
                # The generator properties are not aggregated, should be defined in the root
                # cpp info if needed
            # FIXME: What to do about sysroot?
        # Leave only the aggregated value
        main_value = self.components[None]
        self.components = DefaultOrderedDict(lambda: _NewComponent(none_values=False))
        self.components[None] = main_value

    def copy(self):
        ret = NewCppInfo()
        ret._generator_properties = copy.copy(self._generator_properties)
        ret.components = DefaultOrderedDict(lambda: _NewComponent(none_values=True))
        for comp_name in self.components:
            ret.components[comp_name] = copy.copy(self.components[comp_name])
        return ret

    @property
    def required_components(self):
        """Returns a list of tuples with (require, component_name) required by the package
        If the require is internal (to another component), the require will be None"""
        # FIXME: Cache the value
        ret = []
        for comp in self.components.values():
            ret.extend([r.split("::") for r in comp.requires if "::" in r and r not in ret])
            ret.extend([(None, r) for r in comp.requires if "::" not in r and r not in ret])
        return ret

    def __str__(self):
        ret = []
        for cname, c in self.components.items():
            for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                ret.append("Component: '{}' "
                           "Var: '{}' "
                           "Value: '{}'".format(cname, n, getattr(c, n)))
        return "\n".join(ret)


def fill_old_cppinfo(origin, old_cpp):
    """Copy the values from a new cpp info object to an old one but prioritizing it,
    if the value is not None, then override the declared in the conanfile.cpp_info => (dest)"""

    if origin.has_components:
        # If the user declared components, reset the global values
        origin.components[None] = _NewComponent(none_values=True)
        # COMPONENTS
        for cname, c in origin.components.items():
            if cname is None:
                continue
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                value = getattr(c, varname)
                if value is not None:
                    # Override the self.cpp_info component value
                    setattr(old_cpp.components[cname], varname, copy.copy(value))

            if c.requires is not None:
                old_cpp.components[cname].requires = copy.copy(c.requires)
            if c._generator_properties is not None:
                old_cpp.components[cname]._generator_properties = copy.copy(c._generator_properties)
    else:
        for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            value = getattr(origin, varname)
            if value is not None:
                # Override the self.cpp_info value
                setattr(old_cpp, varname, copy.copy(value))


