def base_tox = """
[tox]
envlist = py27,py34,py36
setenv = CODECOV_TOKEN = f1a9c517-3d81-4213-9f51-61513111fc28
# skipsdist=True
# alwayscopy = True

[testenv]
passenv = *
deps = -rconans/requirements.txt
       -rconans/requirements_dev.txt
       -rconans/requirements_server.txt
commands=nosetests {posargs: conans.test}
         - codecov
"""

def win_tox = {tmpdir -> """
setenv = CONAN_BASH_PATH = c:/tools/msys64/usr/bin/bash


[testenv:py27]
basepython=C:\\Python27\\python.exe

[testenv:py34]
basepython=C:\\Python34\\python.exe

[testenv:py36]
basepython=C:\\Python36\\python.exe
"""}

def mac_tox = """
[testenv:py27]
basepython=/Users/jenkins_ci/.pyenv/versions/2.7.11/bin/python

[testenv:py34]
basepython=/Users/jenkins_ci/.pyenv/versions/3.4.7/bin/python

[testenv:py36]
basepython=/Users/jenkins_ci/.pyenv/versions/3.6.3/bin/python
"""