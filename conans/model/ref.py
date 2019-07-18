import re
from collections import namedtuple

from six import string_types

from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


def get_reference_fields(arg_reference, user_channel_allowed=False):
    """
    :param arg_reference: String with a complete reference, or
        only user/channel (if user_channel_allowed)
        only name/version (if not pattern_is_user_channel)
    :param user_channel_allowed: Two items means user/channel or not.
    :return: name, version, user and channel, in a tuple
    """

    def split_pair(pair, split_char, priority_first=True):
        if not pair:
            return None, None
        if "/" in pair:
            tmp = pair.split(split_char)
            if len(tmp) != 2:
                raise ConanException("The reference has too many '%s'".format(split_char))
            else:
                return tmp
        else:
            return (pair, None) if priority_first else (None, pair)

    if not arg_reference:
        return None, None, None, None, None

    revision = None

    if "#" in arg_reference:
        tmp = arg_reference.split("#", 1)
        revision = tmp[1]
        arg_reference = tmp[0]

    if "@" in arg_reference:
        name_version, user_channel = split_pair(arg_reference, "@")
        name, version = split_pair(name_version, "/", priority_first=False)
        user, channel = split_pair(user_channel, "/")

        user = user or ConanFileReference.DEFAULT_REF_USER
        channel = channel or ConanFileReference.DEFAULT_REF_CHANNEL
        return name, version, user, channel, revision
    else:
        if user_channel_allowed:
            el1, el2 = split_pair(arg_reference, "/")
            return None, None, el1, el2, revision
        else:
            raise ConanException("Invalid reference, specify something like zlib/1.2.11@ "
                                 "if you want to avoid the 'user/channel'")


def check_valid_ref(ref, allow_pattern):
    try:
        if not isinstance(ref, ConanFileReference):
            ref = ConanFileReference.loads(ref, validate=True)
        return "*" not in ref or allow_pattern
    except ConanException:
        pass
    return False


class ConanName(object):
    _max_chars = 51
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars - 1))

    _validation_revision_pattern = re.compile("^[a-zA-Z0-9]{1,%s}$" % _max_chars)

    @staticmethod
    def invalid_name_message(value, reference_token=None):
        if len(value) > ConanName._max_chars:
            reason = "is too long. Valid names must contain at most %s characters."\
                     % ConanName._max_chars
        elif len(value) < ConanName._min_chars:
            reason = "is too short. Valid names must contain at least %s characters."\
                     % ConanName._min_chars
        else:
            reason = ("is an invalid name. Valid names MUST begin with a "
                      "letter, number or underscore, have between %s-%s chars, including "
                      "letters, numbers, underscore, dot and dash"
                      % (ConanName._min_chars, ConanName._max_chars))
        message = "Value provided{ref_token}, '{value}' (type {type}), {reason}".format(
            ref_token=" for {}".format(reference_token) if reference_token else "",
            value=value, type=type(value).__name__, reason=reason
        )
        raise InvalidNameException(message)

    @staticmethod
    def validate_string(value, reference_token=None):
        """Check for string"""
        if not isinstance(value, string_types):
            message = "Value provided{ref_token}, '{value}' (type {type}), {reason}".format(
                ref_token=" for {}".format(reference_token) if reference_token else "",
                value=value, type=type(value).__name__,
                reason="is not a string"
            )
            raise InvalidNameException(message)

    @staticmethod
    def validate_name(name, version=False, reference_token=None):
        """Check for name compliance with pattern rules"""
        ConanName.validate_string(name, reference_token=reference_token)
        if name == "*":
            return
        if ConanName._validation_pattern.match(name) is None:
            if version and name.startswith("[") and name.endswith("]"):
                return
            ConanName.invalid_name_message(name, reference_token=reference_token)

    @staticmethod
    def validate_revision(revision):
        if ConanName._validation_revision_pattern.match(revision) is None:
            raise InvalidNameException("The revision field, must contain only letters "
                                       "and numbers with a length between 1 and "
                                       "%s" % ConanName._max_chars)


class ConanFileReference(namedtuple("ConanFileReference", "name version user channel revision")):
    """ Full reference of a package recipes, e.g.:
    opencv/2.4.10@lasote/testing
    """
    sep_pattern = re.compile(r"([^/]+)/([^/]+)@([^/]+)/([^/#]+)#?(.+)?")

    DEFAULT_REF_USER = "_"
    DEFAULT_REF_CHANNEL = "_"

    def __new__(cls, name, version, user, channel, revision=None, validate=True):
        """Simple name creation.
        @param name:        string containing the desired name
        @param version:     string containing the desired version
        @param user:        string containing the user name
        @param channel:     string containing the user channel
        @param revision:    string containing the revision (optional)
        """
        user = user or cls.DEFAULT_REF_USER
        channel = channel or cls.DEFAULT_REF_CHANNEL

        version = Version(version) if version is not None else None
        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel, revision)
        if validate:
            obj._validate()
        return obj

    def _validate(self):
        ConanName.validate_name(self.name, reference_token="package name")
        ConanName.validate_name(self.version, True, reference_token="package version")
        if self.user != self.DEFAULT_REF_USER:
            ConanName.validate_name(self.user, reference_token="user name")
        if self.channel != self.DEFAULT_REF_CHANNEL:
            ConanName.validate_name(self.channel, reference_token="channel")
        if self.revision:
            ConanName.validate_revision(self.revision)

    @staticmethod
    def loads(text, validate=True):
        """ Parses a text string to generate a ConanFileReference object
        """
        name, version, user, channel, revision = get_reference_fields(text)
        ref = ConanFileReference(name, version, user, channel, revision, validate=validate)
        return ref

    def __repr__(self):
        if self.user == self.DEFAULT_REF_USER and self.channel == self.DEFAULT_REF_CHANNEL:
            return "%s/%s" % (self.name, self.version)
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def full_repr(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        return "%s%s" % (str(self), str_rev)

    def dir_repr(self):
        return "/".join(self[:-1])

    def copy_with_rev(self, revision):
        return ConanFileReference(self.name, self.version, self.user, self.channel, revision)

    def copy_clear_rev(self):
        return ConanFileReference(self.name, self.version, self.user, self.channel, None)


class PackageReference(namedtuple("PackageReference", "ref id revision")):
    """ Full package reference, e.g.:
    opencv/2.4.10@lasote/testing, fe566a677f77734ae
    """

    def __new__(cls, ref, package_id, revision=None, validate=True):
        if "#" in package_id:
            package_id, revision = package_id.rsplit("#", 1)
        obj = super(cls, PackageReference).__new__(cls, ref, package_id, revision)
        if validate:
            obj.validate()
        return obj

    def validate(self):
        if self.revision:
            ConanName.validate_revision(self.revision)

    @staticmethod
    def loads(text, validate=True):
        text = text.strip()
        tmp = text.split(":")
        try:
            ref = ConanFileReference.loads(tmp[0].strip(), validate=validate)
            package_id = tmp[1].strip()
        except IndexError:
            raise ConanException("Wrong package reference %s" % text)
        return PackageReference(ref, package_id, validate=validate)

    def __repr__(self):
        return "%s:%s" % (self.ref, self.id)

    def full_repr(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        tmp = "%s:%s%s" % (self.ref.full_repr(), self.id, str_rev)
        return tmp

    def copy_with_revs(self, revision, p_revision):
        return PackageReference(self.ref.copy_with_rev(revision), self.id, p_revision)

    def copy_clear_rev(self):
        ref = self.ref.copy_clear_rev()
        return PackageReference(ref, self.id, revision=None)

    def copy_clear_revs(self):
        return self.copy_with_revs(None, None)
