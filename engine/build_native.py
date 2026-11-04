"""Build only the scratch extension with the installed compiler and GMP."""
import os
from pathlib import Path
import resource
import subprocess
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
GMP = Path('/opt/homebrew/opt/gmp')


def main():
    assert sys.version_info[:2] == (3, 13)
    assert (GMP / 'include/gmpxx.h').is_file()
    assert (Path(sysconfig.get_path('include')) / 'Python.h').is_file()
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    sdk = Path(subprocess.check_output(['/usr/bin/xcrun', '--show-sdk-path'], text=True).strip())
    headers = sdk / 'usr/include/c++/v1'
    assert all((headers / name).is_file() for name in ('iosfwd', 'vector', 'memory'))
    output = HERE / ('_native_bound' + sysconfig.get_config_var('EXT_SUFFIX'))
    temporary = output.with_suffix(output.suffix + '.tmp')
    subprocess.run(['/usr/bin/clang++', '-std=c++17', '-O3', '-Wall', '-Wextra',
                    '-isysroot', str(sdk), '-isystem', str(headers),
                    '-bundle', '-undefined', 'dynamic_lookup',
                    '-I' + sysconfig.get_path('include'), '-I' + str(GMP / 'include'),
                    str(HERE / 'native_bound.cpp'), '-L' + str(GMP / 'lib'),
                    '-Wl,-rpath,' + str(GMP / 'lib'), '-lgmpxx', '-lgmp',
                    '-o', str(temporary)], check=True, timeout=120)
    os.replace(temporary, output)


if __name__ == '__main__':
    main()
