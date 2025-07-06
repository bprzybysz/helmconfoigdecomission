**Error Context:**
```
Exit code: 2
Output:
Prepared 3 packages in 2.11s                                      
Installed 60 packages in 62ms                                     
 + annotated-types==0.7.0                                                                                                   
 + anyio==4.9.0                                                   
 + attrs==25.3.0                                                     
 + authlib==1.6.0                                                                                                           
 + black==25.1.0                                                     
 + certifi==2025.6.15                                                                                                       
 + cffi==1.17.1
 + charset-normalizer==3.4.2
 + click==8.2.1
 + coverage==7.9.2
 + cryptography==45.0.5
 + dnspython==2.7.0
 + email-validator==2.2.0
 + exceptiongroup==1.3.0
 + fastmcp==2.10.2
 + helm-config-decommission-tool==0.1.0 (from file:///Users/blaisem4/src/helmconfoigdecomission)
 + h11==0.16.0
 + httpcore==1.0.9
 + httpx==0.28.1
 + httpx-sse==0.4.1
 + idna==3.10
 + iniconfig==2.1.0
 + jsonschema==4.24.0
 + jsonschema-specifications==2025.4.1
 + markdown-it-py==3.0.0
 + mcp==1.10.1
 + mdurl==0.1.2
 + mypy==1.16.1
 + mypy-extensions==1.1.0
 + openapi-pydantic==0.5.1
 + packaging==25.0
 + pathspec==0.12.1
 + platformdirs==4.3.8
 + pluggy==1.6.0
 + pycparser==2.22
 + pydantic==2.11.7
 + pydantic-core==2.33.2
 + pydantic-settings==2.10.1
 + pygments==2.19.2
 + pytest==8.4.1
 + pytest-cov==6.2.1
 + pytest-mock==3.14.1
 + python-dotenv==1.1.1
 + python-multipart==0.0.20
 + pyyaml==6.0.2
 + referencing==0.36.2
 + requests==2.32.4
 + rich==14.0.0
 + rpds-py==0.26.0
 + ruff==0.12.2
 + shellingham==1.5.4
 + sniffio==1.3.1
 + sse-starlette==2.3.6
 + starlette==0.47.1
 + typer==0.16.0
 + typing-extensions==4.14.1
 + typing-inspection==0.4.1
 + urllib3==2.5.0
 + uv==0.7.19
 + uvicorn==0.35.0
✅ Dependencies installed in .venv
🔍 Running linter (ruff)...
decommission_tool.py:1:8: F401 [*] `os` imported but unused   
  |
1 | import os
  |        ^^ F401
2 | import re
3 | import sys
  |
  = help: Remove unused import: `os`

decommission_tool.py:7:39: F401 [*] `typing.Optional` imported but unused
  |
5 | import logging
6 | from pathlib import Path
7 | from typing import List, Dict, Tuple, Optional, Any
  |                                       ^^^^^^^^ F401
8 | import yaml
9 | import subprocess
  |
  = help: Remove unused import: `typing.Optional`

decommission_tool.py:9:8: F401 [*] `subprocess` imported but unused
   |
 7 | from typing import List, Dict, Tuple, Optional, Any
 8 | import yaml
 9 | import subprocess
   |        ^^^^^^^^^^ F401
10 | from git_utils import GitRepository
   |
   = help: Remove unused import: `subprocess`

decommission_tool.py:290:5: F811 Redefinition of unused `main` from line 15
    |
288 |     return "\n".join(summary_lines), "\n".join(plan_lines)
289 | 
290 | def main():
    |     ^^^^ F811
291 |     """Main function to parse arguments and run the tool."""
292 |     parser = argparse.ArgumentParser(
    |
    = help: Remove definition: `main`

git_utils.py:3:26: F401 [*] `typing.Dict` imported but unused
  |
1 | import subprocess
2 | from pathlib import Path
3 | from typing import List, Dict, Optional, Callable, Any
  |                          ^^^^ F401
4 | import logging
5 | from functools import wraps
  |
  = help: Remove unused import

git_utils.py:3:42: F401 [*] `typing.Callable` imported but unused
  |
1 | import subprocess
2 | from pathlib import Path
3 | from typing import List, Dict, Optional, Callable, Any
  |                                          ^^^^^^^^ F401
4 | import logging
5 | from functools import wraps
  |
  = help: Remove unused import

git_utils.py:3:52: F401 [*] `typing.Any` imported but unused
  |
1 | import subprocess
2 | from pathlib import Path
3 | from typing import List, Dict, Optional, Callable, Any
  |                                                    ^^^ F401
4 | import logging
5 | from functools import wraps
  |
  = help: Remove unused import

git_utils.py:5:23: F401 [*] `functools.wraps` imported but unused
  |
3 | from typing import List, Dict, Optional, Callable, Any
4 | import logging
5 | from functools import wraps
  |                       ^^^^^ F401
6 | import inspect
  |
  = help: Remove unused import: `functools.wraps`

git_utils.py:6:8: F401 [*] `inspect` imported but unused
  |
4 | import logging
5 | from functools import wraps
6 | import inspect
  |        ^^^^^^^ F401
7 | 
8 | class GitRepository:
  |
  = help: Remove unused import: `inspect`

tests/conftest.py:1:8: F401 [*] `pytest` imported but unused
  |
1 | import pytest
  |        ^^^^^^ F401
2 | 
3 | def pytest_addoption(parser):
  |
  = help: Remove unused import: `pytest`

tests/test_container_e2e.py:2:8: F401 [*] `os` imported but unused
  |
1 | # tests/test_container_e2e.py
2 | import os
  |        ^^ F401
3 | import subprocess
4 | import time
  |
  = help: Remove unused import: `os`

tests/test_container_e2e.py:7:8: F401 [*] `yaml` imported but unused
  |
5 | from pathlib import Path
6 | import pytest
7 | import yaml
  |        ^^^^ F401
8 | 
9 | # Define constants for compose file and container name
  |
  = help: Remove unused import: `yaml`

tests/test_decommission_tool.py:2:8: F401 [*] `tempfile` imported but unused
  |
1 | import pytest
2 | import tempfile
  |        ^^^^^^^^ F401
3 | import json
4 | import shutil
  |
  = help: Remove unused import: `tempfile`

tests/test_decommission_tool.py:3:8: F401 [*] `json` imported but unused
  |
1 | import pytest
2 | import tempfile
3 | import json
  |        ^^^^ F401
4 | import shutil
5 | import subprocess
  |
  = help: Remove unused import: `json`

tests/test_decommission_tool.py:8:34: F401 [*] `unittest.mock.mock_open` imported but unused
   |
 6 | import sys
 7 | from pathlib import Path
 8 | from unittest.mock import patch, mock_open
   |                                  ^^^^^^^^^ F401
 9 | 
10 | # Add project root to sys.path
   |
   = help: Remove unused import: `unittest.mock.mock_open`

tests/test_decommission_tool.py:169:12: E721 Use `is` and `is not` for type comparisons, or `isinstance()` for isinstance checks
    |
167 |     with patch('sys.argv', ['decommission_tool.py', invalid_path, 'test_db']), pytest.raises(SystemExit) as e:
168 |         main()
169 |     assert e.type == SystemExit
    |            ^^^^^^^^^^^^^^^^^^^^ E721
170 |     assert e.value.code == 1
171 |     captured = capsys.readouterr()
    |

tests/test_file_system_mcp_server.py:3:8: F401 [*] `os` imported but unused
  |
1 | import pytest
2 | from pathlib import Path
3 | import os
  |        ^^ F401
4 | import sys
5 | import shutil
  |
  = help: Remove unused import: `os`

tests/test_file_system_mcp_server.py:5:8: F401 [*] `shutil` imported but unused
  |
3 | import os
4 | import sys
5 | import shutil
  |        ^^^^^^ F401
6 | import subprocess
  |
  = help: Remove unused import: `shutil`

tests/test_remove_functionality.py:2:8: F401 [*] `tempfile` imported but unused
  |
1 | import pytest
2 | import tempfile
  |        ^^^^^^^^ F401
3 | import textwrap
4 | import yaml
  |
  = help: Remove unused import: `tempfile`

tests/test_remove_functionality.py:6:59: F401 [*] `decommission_tool.generate_summary_and_plan` imported but unused
  |
4 | import yaml
5 | from pathlib import Path
6 | from decommission_tool import PostgreSQLDecommissionTool, generate_summary_and_plan
  |                                                           ^^^^^^^^^^^^^^^^^^^^^^^^^ F401
7 | 
8 | @pytest.fixture
  |
  = help: Remove unused import: `decommission_tool.generate_summary_and_plan`

Found 20 errors.
[*] 18 fixable with the `--fix` option.
make[1]: *** [lint] Error 1
make: *** [ci] Error 2
```

**Perplexity Answer:**
```
The error occurs because the **py_modules** key is not allowed in the [project] table of pyproject.toml. Instead, for projects using a flat layout (where your modules are .py files at the project root), you must use the [tool.setuptools] table to declare them, not [project][1][2][3].

Here’s how to fix your pyproject.toml for a flat-layout project using setuptools (with only top-level .py modules, not a package directory):

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "helm-config-decommission-tool"
version = "0.1.0"
description = "A tool to decommission PostgreSQL databases from a Helm-based infrastructure."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT License" }
classifiers = [
    "Programming Language :: Python :: 3",
    "Operating System :: OS Independent",
]
dependencies = [
    "fastmcp",
    "pyyaml",
    "requests"
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-mock",
    "pytest-cov",
    "ruff",
    "mypy",
    "black",
    "uv"
]

[project.scripts]
decommission-tool = "decommission_tool:main"

[tool.setuptools]
py-modules = ["decommission_tool", "git_utils", "mcp_server_main", "file_system_mcp_server"]
```

Key points:

- **py_modules** (or **py-modules** in TOML) must go under the [tool.setuptools] table, not [project][1][2].
- Your .py files (e.g., decommission_tool.py) must be at the root of your project directory.
- This tells setuptools to include those specific modules when building your project[2][3].

For reference, only certain metadata fields are allowed in the [project] table. Module/package configuration (py-modules or packages) is handled by the build backend’s tool-specific section—here, [tool.setuptools][1].

You can find relevant examples in the official setuptools documentation[1][3].

**Summary Table: pyproject.toml configuration for flat layout**

| Section             | Setting      | Value / Example                                                           |
|---------------------|-------------|---------------------------------------------------------------------------|
| [project]           | name, etc.   | Standard project metadata fields                                          |
| [tool.setuptools]   | py-modules   | ["decommission_tool", "git_utils", ...]                                   |

If you want, you can also remove [tool.setuptools] and use the default behavior—setuptools will attempt to autodiscover .py files at the root, but explicitly specifying py-modules makes your configuration robust[3].

**Do not** place py_modules or py-modules inside the [project] table—this is not supported and will result in configuration errors[1][2].

Citations:
[1] https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
[2] https://github.com/pypa/build/issues/611
[3] https://setuptools.pypa.io/en/latest/userguide/package_discovery.html
[4] https://discuss.python.org/t/trouble-using-setuptools-with-only-a-pyproject-toml-file/48655
[5] https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html
```
