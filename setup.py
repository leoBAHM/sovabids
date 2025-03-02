import setuptools

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

REQUIREMENTS = [i.strip() for i in open("requirements.txt").readlines()]

setuptools.setup(
    name="sovabids",
    version="0.0.1",
    author="Yorguin Mantilla",
    description="Automated eeg2bids conversion",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    packages=setuptools.find_packages(),
    #install_requires = ['mne_bids','requests','pybv','pyyaml','pandas'],
    install_requires = REQUIREMENTS,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points = {'console_scripts':[
        'sovapply = sovabids.rules:sovapply',
        'sovaconvert = sovabids.convert:sovaconvert'
        ]}
)
