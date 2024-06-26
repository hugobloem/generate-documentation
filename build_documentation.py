#!/usr/bin/env python
"""Generate documentation for each module in a package."""

import logging
import os
from argparse import ArgumentParser

from pydoc_markdown import PydocMarkdown
from pydoc_markdown.contrib.loaders.python import PythonLoader
from pydoc_markdown.interfaces import Context

logger = logging.getLogger(__name__)


class RenderSession:
    """Represents a rendering session for PydocMarkdown.

    Args:
        config (None | dict | str): Configuration object or file.
        render_toc (bool | None, optional): Override the "render_toc" option in the MarkdownRenderer.
        search_path (list[str] | None, optional): Override the search path in the Python loader.
        modules (list[str] | None, optional): Override the modules in the Python loader.
        packages (list[str] | None, optional): Override the packages in the Python loader.
        py2 (bool | None, optional): Override Python2 compatibility in the Python loader.

    Attributes:
        config: The configuration object or file.
        render_toc: The overridden "render_toc" option in the MarkdownRenderer.
        search_path: The overridden search path in the Python loader.
        modules: The overridden modules in the Python loader.
        packages: The overridden packages in the Python loader.
        py2: The overridden Python2 compatibility in the Python loader.

    Methods:
        _apply_overrides: Apply overrides to the PydocMarkdown configuration based on command-line options.
        load: Load the configuration for PydocMarkdown.
        render: Render the documentation using the provided configuration.

    """

    def __init__(
        self,
        config: None | dict | str,
        render_toc: bool | None = None,
        search_path: list[str] | None = None,
        modules: list[str] | None = None,
        packages: list[str] | None = None,
        py2: bool | None = None,
    ) -> None:
        """Initialize the BuildDocumentation object.

        Args:
            config (None | dict | str): The configuration for the documentation build.
            render_toc (bool | None, optional): Whether to render the table of contents. Defaults to None.
            search_path (list[str] | None, optional): The search path for modules and packages. Defaults to None.
            modules (list[str] | None, optional): The list of modules to include in the documentation. Defaults to None.
            packages (list[str] | None, optional): The list of packages to include in the documentation. Defaults to None.
            py2 (bool | None, optional): Whether the code is written in Python 2. Defaults to None.

        """
        self.config = config
        self.render_toc = render_toc
        self.search_path = search_path
        self.modules = modules
        self.packages = packages
        self.py2 = py2

    def _apply_overrides(self, config: PydocMarkdown):
        """Apply overrides to the PydocMarkdown configuration based on command-line options.

        Args:
            config (PydocMarkdown): The PydocMarkdown configuration object.

        Raises:
            ValueError: If no python loader is found in the configuration.

        """
        # Update configuration per command-line options.
        if self.modules or self.packages or self.search_path or self.py2 is not None:
            loader = next(
                (
                    conf_loader
                    for conf_loader in config.loaders
                    if isinstance(conf_loader, PythonLoader)
                ),
                None,
            )
            if not loader:
                raise ValueError("no python loader found")
            if self.modules:
                loader.modules = self.modules
            if self.packages:
                loader.packages = self.packages
            if self.search_path:
                loader.search_path = self.search_path
            if self.py2 is not None:
                loader.parser.print_function = not self.py2

    def load(self) -> PydocMarkdown:
        """Load the configuration for PydocMarkdown.

        Returns:
            PydocMarkdown: A PydocMarkdown object representing the loaded configuration.

        """
        config = PydocMarkdown()
        if self.config:
            config.load_config(self.config)
        self._apply_overrides(config)

        if isinstance(self.config, str):
            config.init(
                Context(directory=os.path.dirname(os.path.abspath(self.config)))
            )

        if config.unknown_fields:
            logger.warning(
                "Unknown configuration options:\n%s\n",
                "\n------\n".join(config.unknown_fields),
            )

        return config

    def render(self, config: PydocMarkdown) -> list[str]:
        """Render the documentation using the provided configuration.

        Args:
            config (PydocMarkdown): The configuration object.

        Returns:
            list[str]: A list of filenames to watch for changes.

        """
        modules = config.load_modules()
        config.process(modules)
        config.render(modules)

        watch_files = {m.location.filename for m in modules}
        if isinstance(self.config, str):
            watch_files.add(self.config)

        return list(watch_files)


def file2module(file, path):
    """Convert a file path to a module name.

    Args:
        file (str): The file path.
        path (str): The common path prefix to remove from the file path.

    Returns:
        str: The module name.

    Example:
        >>> file2module('/home/hugo/erptools/scripts/build_documentation.py', '/home/hugo/erptools/scripts')
        'build_documentation'

    """
    file = file.removeprefix(path)
    file = file.removesuffix(".py")
    parts = [part for part in file.split("/") if part]
    return ".".join(parts)


def main(
    config: str,
    package_dir: str,
    docs_dir: str,
    skip_files: list[str],
    src_files: list[str] = None,
):
    """Generate the main function documentation.

    Args:
        config (str): Path to the configuration file.
        package_dir (str): Directory containing the package files.
        docs_dir (str): Directory to store the generated documentation.
        skip_files (list[str]): List of files to skip during documentation generation.
        src_files (list[str], optional): List of source files to process. Defaults to None.

    """
    if not package_dir.endswith("/"):
        package_dir += "/"
    if not docs_dir.endswith("/"):
        docs_dir += "/"

    package_name = package_dir.split("/")[-2]

    if src_files is None:
        src_files = []
        for root, _, files in os.walk(package_dir):
            for _file in files:
                if _file.endswith(".py") and _file not in skip_files:
                    src_files.append(os.path.join(root, _file))

    # Create an instance of the RenderSession class

    render_toc = True
    search_path = [package_dir]
    packages = []
    py2 = False

    for file in src_files:
        if os.path.basename(file) in skip_files or package_name not in file:
            continue
        logging.info("Processing file: %s", file)
        modules = [file2module(file, package_dir)]
        output_file = file.replace(package_dir, docs_dir).replace(".py", ".md")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        session = RenderSession(
            config,
            render_toc,
            search_path,
            modules,
            packages,
            py2,
        )

        pydocmd = session.load()
        pydocmd.renderer.filename = output_file
        session.render(pydocmd)


if __name__ == "__main__":
    """Run the main function."""
    parser = ArgumentParser()

    parser.add_argument("-c", "--config", default="./pydoc-markdown.yml")
    parser.add_argument("-p", "--package_dir", default="erptools/")
    parser.add_argument("-d", "--docs_dir", default="./docs/erptools/")
    parser.add_argument("-f", "--files", nargs="*")
    parser.add_argument(
        "-s", "--skip_files", nargs="*", default=["__init__.py", "version.py"]
    )

    args = parser.parse_args()

    main(
        config=args.config,
        package_dir=args.package_dir,
        docs_dir=args.docs_dir,
        skip_files=args.skip_files,
        src_files=args.files,
    )
