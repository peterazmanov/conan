import os

from conf import winpylocation, linuxpylocation, macpylocation, Extender
import platform


pylocations = {"Windows": winpylocation,
               "Linux": linuxpylocation,
               "Darwin": macpylocation}[platform.system()]


def run_tests(module_path, pyver, source_folder, tmp_folder, exluded_tags, num_cores=4, verbosity=2):

    venv_dest = os.path.join(tmp_folder, "venv")
    exluded_tags = " ".join(["-a '!%s'" % tag for tag in exluded_tags])
    pyenv = pylocations[pyver]
    # pyenv = "/usr/local/bin/python2"

    command = "cd {source_folder} && " \
              "virtualenv --python {pyenv} {venv_dest} && " \
              "source {venv_dest}/bin/activate && " \
              "pip install -r conans/requirements.txt && " \
              "pip install -r conans/requirements_dev.txt && " \
              "pip install -r conans/requirements_server.txt && " \
              "nosetests {module_path} --verbosity={verbosity} --processes={num_cores} " \
              "--process-timeout=1000 " \
              "{excluded_tags}".format(**{"module_path": module_path,
                                          "pyenv": pyenv,
                                          "source_folder": source_folder,
                                          "tmp_folder": tmp_folder,
                                          "excluded_tags": exluded_tags,
                                          "venv_dest": venv_dest,
                                          "num_cores": num_cores,
                                          "verbosity": verbosity})

    run(command)


def run(command):
    import subprocess
    print("--CALLING: %s" % command)
    # ret = subprocess.call("bash -c '%s'" % command, shell=True)
    ret = subprocess.call(command, shell=True, executable='/bin/bash')
    if ret != 0:
        raise Exception("Error running: '%s'" % command)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Launch tests in a venv')
    parser.add_argument('module', help='e.j: conans.test')
    parser.add_argument('pyver', help='e.j: py27')
    parser.add_argument('source_folder', help='Folder containing the conan source code')
    parser.add_argument('tmp_folder', help='Folder to create the venv inside')
    parser.add_argument('--exclude', '-e', nargs=1, action=Extender,
                        help='Tags to exclude from testing, e.j: rest_api')

    args = parser.parse_args()
    run_tests(args.module, args.pyver, args.source_folder, args.tmp_folder, args.exclude)


