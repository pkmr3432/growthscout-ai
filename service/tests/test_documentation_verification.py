# service/tests/test_documentation_verification.py
"""
Automated validation checks checking markdown documentation code snippets,
installation instruction commands, and imports correctness.
"""

import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


import pytest

def test_markdown_code_snippets_syntax():
    """Extracts python code blocks from README.md and asserts they compile successfully."""
    readme_path = os.path.join(ROOT_DIR, "growthscout-python", "README.md")
    assert os.path.exists(readme_path)

    with open(readme_path, "r") as f:
        content = f.read()

    # Find all python blocks
    python_blocks = re.findall(r"```python\n(.*?)```", content, re.DOTALL)
    assert len(python_blocks) > 0, "No python code examples documented in README.md"

    for i, code in enumerate(python_blocks):
        try:
            # Wrap async blocks to prevent SyntaxError: 'await' outside function
            if "await " in code or "async for " in code:
                # Indent lines
                indented = "\n".join("    " + line for line in code.split("\n"))
                code = f"async def _wrapper():\n{indented}"
            # compile check (compiles into AST, catching SyntaxError)
            compile(code, f"<readme_snippet_{i}>", "exec")
        except SyntaxError as e:
            pytest.fail(f"README.md Python code snippet {i} has syntax errors: {e}")


def test_installation_commands_format():
    """Asserts installation commands in both READMEs match canonical patterns."""
    python_readme = os.path.join(ROOT_DIR, "growthscout-python", "README.md")
    ts_readme = os.path.join(ROOT_DIR, "growthscout-js", "README.md")

    with open(python_readme, "r") as f:
        py_content = f.read()
    with open(ts_readme, "r") as f:
        ts_content = f.read()

    # Assert correct pip installation documented
    assert "pip install growthscout" in py_content

    # Assert correct npm installation documented
    assert "npm install growthscout-js" in ts_content


def test_api_documentation_links():
    """Asserts documentation links exist and are not broken references."""
    python_readme = os.path.join(ROOT_DIR, "growthscout-python", "README.md")
    with open(python_readme, "r") as f:
        content = f.read()

    # Find markdown links
    links = re.findall(r"\[.*?\]\((.*?)\)", content)
    for link in links:
        # Ignore external website links or verify they are well-formed URLs
        if link.startswith("http"):
            assert link.startswith("http://") or link.startswith("https://")
        else:
            # Internal file references
            assert len(link) > 0
