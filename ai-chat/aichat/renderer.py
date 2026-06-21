import re
import click

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.theme import Theme
    from rich.status import Status
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
class MarkdownRenderer:
    def __init__(self):
        self.buffer = ''
        self.state = 'NORMAL'
        self.status = None
        self.block_lines = []
        self.full_reply = ''
        if RICH_AVAILABLE:
            custom_theme = Theme({
                "markdown.h1": "bold magenta",
                "markdown.h2": "bold magenta",
            })
            self.console = Console(theme=custom_theme)
        else:
            self.console = None

    def _stop_status(self):
        if self.status:
            self.status.stop()
            self.status = None

    def _render_header(self, line: str):
        if not self.console:
            return False
        stripped_line = line.strip()
        header_match = re.match(r'^(#+)\s*(.*)', stripped_line)
        if not header_match:
            return False
        level = len(header_match.group(1))
        title = header_match.group(2).strip()
        title = re.sub(r'\*\*(.*?)\*\*', r'\1', title)
        level = min(max(level, 1), 6)
        header_colors = {
            1: "magenta", 2: "cyan", 3: "green", 4: "yellow", 5: "bright_blue", 6: "bright_black"
        }
        color = header_colors.get(level, "white")
        if level == 1:
            self.console.print(f"\n[bold white on {color}] {title.upper()} [/bold white on {color}]")
        elif level == 2:
            self.console.print(f"\n[bold {color}]┃ {title}[/bold {color}]")
        elif level == 3:
            self.console.print(f"\n[bold {color}]◆ {title}[/bold {color}]")
        else:
            prefixes = {4: "◇", 5: "◈", 6: "○"}
            prefix = prefixes.get(level, "•")
            self.console.print(f"\n[bold {color}]{prefix} {title}[/bold {color}]")
        return True

    def _flush_block(self):
        if not self.block_lines:
            return
        self._stop_status()
        content = '\n'.join(self.block_lines)
        if not RICH_AVAILABLE:
            self.block_lines = []
            self.state = 'NORMAL'
            return
        if self.state == 'CODE':
            lines = content.split('\n', 1)
            if len(lines) > 1 and lines[0].isalnum():
                lang, code = lines[0], lines[1]
            else:
                lang, code = "", content
            syntax = Syntax(
                code.strip(),
                lang or "text",
                theme="monokai",
                background_color="default",
                word_wrap=True,
                indent_guides=False
            )
            panel = Panel(syntax, border_style="bright_blue", expand=False, title=lang if lang else None, title_align="right")
            self.console.print(panel)
        elif self.state in ('TABLE', 'LIST', 'NORMAL'):
            remaining_lines = []
            for line in self.block_lines:
                if line.strip().startswith('#') and not self.state == 'CODE':
                    if remaining_lines:
                        self.console.print(Markdown('\n'.join(remaining_lines)))
                        remaining_lines = []
                    if self._render_header(line):
                        continue
                remaining_lines.append(line)
            if remaining_lines:
                self.console.print(Markdown('\n'.join(remaining_lines)))
        self.block_lines = []
        self.state = 'NORMAL'

    def render(self, chunks) -> str:
        first_chunk = True
        for chunk in chunks:
            if first_chunk and RICH_AVAILABLE:
                self.status = Status("[bold blue]正在生成响应...[/bold blue]", spinner="dots")
                self.status.start()
                first_chunk = False
            delta = chunk['choices'][0]['delta'].get('content', '')
            if not delta:
                continue
            self.full_reply += delta
            self.buffer += delta
            if not RICH_AVAILABLE:
                click.echo(delta, nl=False)
                continue
            while '```' in self.buffer:
                if self.state != 'CODE':
                    parts = self.buffer.split('```', 1)
                    if parts[0].strip() or self.block_lines:
                        if parts[0].strip():
                            self.block_lines.extend(parts[0].split('\n'))
                        self._flush_block()
                    self.state = 'CODE'
                    self.buffer = parts[1]
                    self.status = Status("[bold blue]正在生成代码...[/bold blue]", spinner="dots")
                    self.status.start()
                else:
                    parts = self.buffer.split('```', 1)
                    self.block_lines.append(parts[0])
                    self._flush_block()
                    self.state = 'NORMAL'
                    self.buffer = parts[1]
            if '\n' in self.buffer:
                lines = self.buffer.split('\n')
                finished_lines = lines[:-1]
                self.buffer = lines[-1]
                for line in finished_lines:
                    stripped = line.strip()
                    if not stripped and self.state == 'NORMAL':
                        if self.block_lines:
                            self._flush_block()
                        continue
                    is_header = stripped.startswith('#')
                    is_list = (
                        stripped.startswith(('-', '*', '+')) or
                        (stripped and stripped[0].isdigit() and ('. ' in stripped[:4] or ' ' in stripped[:4])) or
                        stripped.startswith(('[ ]', '[x]', '[X]'))
                    )
                    is_table = '|' in stripped
                    new_state = self.state
                    if self.state == 'CODE':
                        new_state = 'CODE'
                    elif is_header:
                        new_state = 'NORMAL'
                    elif is_table:
                        new_state = 'TABLE'
                    elif is_list:
                        new_state = 'LIST'
                    else:
                        new_state = 'NORMAL'
                    if new_state != self.state:
                        if self.state != 'NORMAL':
                            self._flush_block()
                        self.state = new_state
                        if RICH_AVAILABLE:
                            if self.state == 'TABLE':
                                self.status = Status("[bold blue]正在生成表格...[/bold blue]", spinner="dots")
                                self.status.start()
                            elif self.state == 'LIST':
                                self.status = Status("[bold blue]正在生成列表...[/bold blue]", spinner="dots")
                                self.status.start()
                    self.block_lines.append(line)
        if self.buffer:
            self.block_lines.append(self.buffer)
        self._flush_block()
        if not RICH_AVAILABLE and not self.buffer.endswith('\n'):
            click.echo('')
        return self.full_reply


def print_streaming_chunks(chunks) -> str:
    return MarkdownRenderer().render(chunks)


def render_non_streaming_reply(text: str) -> None:
    if RICH_AVAILABLE:
        console = Console()
        console.print(Panel(Markdown(text), border_style="bright_blue"))
    else:
        click.echo(text)
