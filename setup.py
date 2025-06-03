"""Setup script for config-coordination package"""

from setuptools import setup, find_packages

setup(
    name="config-coordination",
    version="20250602_000000_0_1_0_1",
    author="Worker 2",
    description="Configuration coordination service with file-based management and service registry",
    long_description="Rapid deployment configuration service for coordinating multiple services with file-based configuration and service discovery",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.7",
    install_requires=[
        "pyyaml>=5.0.0",
    ],
    extras_require={
        "dev": ["pytest>=6.0", "pytest-cov", "black", "flake8"],
        "server": ["fastapi>=0.68.0", "uvicorn>=0.15.0"]  # For HTTP API server
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
)