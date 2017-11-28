import argparse

winpylocation = {"py27": "C:\\Python27\\python.exe",
                 "py34": "C:\\Python34\\python.exe",
                 "py36": "C:\\Python36\\python.exe"}

macpylocation = {"py27": "/Users/jenkins_ci/.pyenv/versions/2.7.11/bin/python",
                 "py34": "/Users/jenkins_ci/.pyenv/versions/3.4.7/bin/python",
                 "py36": "/Users/jenkins_ci/.pyenv/versions/3.6.3/bin/python"}

linuxpylocation = {"py27": "/Users/jenkins_ci/.pyenv/versions/2.7.11/bin/python",
                   "py34": "/Users/jenkins_ci/.pyenv/versions/3.4.7/bin/python",
                   "py36": "/Users/jenkins_ci/.pyenv/versions/3.6.3/bin/python"}


#def get_
#win_env = {"CONAN_BASH_PATH": "c:/tools/msys64/usr/bin/bash",
#           "CONAN_USER_HOME_SHORT": "%s\\.conan}


class Extender(argparse.Action):
    """Allows to use the same flag several times in a command and creates a list with the values.
       For example:
           conan install MyPackage/1.2@user/channel -o qt:value -o mode:2 -s cucumber:true
           It creates:
           options = ['qt:value', 'mode:2']
           settings = ['cucumber:true']
    """
    def __call__(self, parser, namespace, values, option_strings=None):  # @UnusedVariable
        # Need None here incase `argparse.SUPPRESS` was supplied for `dest`
        dest = getattr(namespace, self.dest, None)
        if not hasattr(dest, 'extend') or dest == self.default:
            dest = []
            setattr(namespace, self.dest, dest)
            # if default isn't set to None, this method might be called
            # with the default as `values` for other arguments which
            # share this destination.
            parser.set_defaults(**{self.dest: None})

        try:
            dest.extend(values)
        except ValueError:
            dest.append(values)