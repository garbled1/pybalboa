from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='pybalboa',
      version='0.3',
      description='Module to communicate with a Balboa spa wifi adapter',
      long_description='Module to communicate with a Balboa spa wifi adapter',
      url='https://github.com/garbled1/pybalboa',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Software Development :: Libraries :: Python Modules'
      ],
      author='Tim Rightnour',
      author_email='root@garbled.net',
      license='Apache 2.0',
      packages=['pybalboa'],
      install_requires=[
          'numpy',
      ],
      include_package_data=True,
      zip_safe=False)
