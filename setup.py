from setuptools import setup, find_packages

with open("requirements.txt", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="gpu_monitor",
    version="0.1.0",
    author="Edoardo Pona",
    author_email="edoardo.pona@gmail.com",
    description="A GPU monitoring dashboard using nvidia-smi and rich",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gpu_monitor = gpu_monitor.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
