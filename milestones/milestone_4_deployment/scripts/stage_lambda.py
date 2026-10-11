"""Stage only the existing Python runtime modules for SAM; no backend duplication.

Inputs: repository Milestone 1B/2 modules. Output: generated build/lambda tree.
No network or AWS operations occur. Run from any working directory.
"""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
OUTPUT = HERE.parents[1] / "build" / "lambda"
DEPENDENCIES = """fastapi>=0.115,<1
mangum>=0.19,<1
boto3>=1.34,<2
python-dotenv>=1,<2
"""


def stage(root=ROOT, output=OUTPUT):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents and output.name != 'lambda':
        raise ValueError("Staging destination must be a dedicated lambda directory")
    output.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(output / "milestones", ignore_errors=True)
    dst = output / "milestones"
    dst.mkdir(parents=True)
    shutil.copy2(root / "milestones" / "__init__.py", dst / "__init__.py")
    for block in ("milestone_1b_federation", "milestone_2_api"):
        shutil.copytree(
            root / "milestones" / block, dst / block,
            ignore=shutil.ignore_patterns(
                "tests", "docs", "examples", "__pycache__", "*.pyc", "README.md", "DATA_README.md"
            ),
        )
    (output / "requirements.txt").write_text(DEPENDENCIES, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"Staged Lambda runtime at: {stage()}")
