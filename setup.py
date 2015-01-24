from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='metarunlog',
      version='0.1',
      description='Metarunlog experiment management system.',
      long_description = readme(),
      url='http://github.com/tomsercu/metarunlog',
      author='Tom Sercu',
      author_email='tom.sercu@gmail.com',
      license='MIT-BSD-NoIdea',
      packages=['metarunlog'],
      install_requires=[
          'jinja2',
      ],
      scripts = ['bin/mrl'],
      zip_safe=False)
