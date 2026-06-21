import json

import click
from byksdk import plugin, PluginContext
from rich.console import Console
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style

from .service import (
    AIService,
    AIServiceError,
    ChatRequest,
    extract_assistant_reply,
)
from . import renderer as ai_renderer

console = Console()

DEFAULT_CONFIG = {
    'model': 'deepseek-v4-flash',
    'api_url': 'https://api.deepseek.com/v1/chat/completions',
    'api_key': None,
    'stream': True,
    'rich': True,
    'extra_body': None,
}

SYSTEM_PROMPT = (
    "You are a helpful assistant. Respond in plain text suitable for a console environment. "
    "Avoid using Markdown, code blocks, or any rich formatting. "
    "Use simple line breaks and spaces for alignment."
)
SYSTEM_PROMPT_RICH = (
    "You are a helpful assistant. Respond using standard Markdown. "
    "Use code blocks for code, bold for emphasis, and lists where appropriate. "
    "Keep your responses concise and suitable for a terminal environment."
)


def _print_streaming_chunks(chunks) -> str:
    reply = ''
    console.print('[bold blue]AI:[/bold blue] ', end='')
    for chunk in chunks:
        delta = chunk['choices'][0]['delta'].get('content', '')
        if delta:
            click.echo(delta, nl=False)
            reply += delta
    click.echo('')
    return reply


pt_style = Style.from_dict({'prompt': 'bold #ffff00'})


def _interactive_setup(state_config: dict) -> bool:
    """交互式配置向导。按 Enter 使用默认值，输入新值则更新配置。
    
    Returns: True if any config was changed.
    """
    console.print()
    console.print('⚙️  [bold cyan]AI 配置设置[/bold cyan]')
    console.print('[dim]按 Enter 使用方括号中的默认值，输入新值后按 Enter 更新。[/dim]\n')
    
    changed = False

    # --- Model ---
    current = state_config.get('model', DEFAULT_CONFIG['model'])
    value = prompt(
        [('class:prompt', f'  Model [{current}]: ')],
        default=str(current),
        style=pt_style,
    ).strip()
    if value and value != str(current):
        state_config['model'] = value
        changed = True

    # --- API Key ---
    has_key = bool(state_config.get('api_key'))
    if has_key:
        console.print(f'  [bold yellow]API Key:[/bold yellow] [dim][{"*" * 12}][/dim]  [dim](按 Enter 保持不变)[/dim]')
    else:
        console.print('  [bold yellow]API Key:[/bold yellow] [dim][(未设置)][/dim]')
    value = prompt(
        [('class:prompt', '  > ')],
        is_password=True,
        style=pt_style,
    ).strip()
    if value:
        state_config['api_key'] = value
        changed = True

    # --- API URL ---
    current = state_config.get('api_url', DEFAULT_CONFIG['api_url'])
    value = prompt(
        [('class:prompt', f'  API URL [{current}]: ')],
        default=str(current),
        style=pt_style,
    ).strip()
    if value and value != str(current):
        state_config['api_url'] = value
        changed = True

    # --- Stream ---
    current = state_config.get('stream', DEFAULT_CONFIG['stream'])
    if isinstance(current, str):
        current = current.lower() in ('1', 'true')
    current_bool = bool(current)
    suffix = '[Y/n]' if current_bool else '[y/N]'
    answer = prompt(
        [('class:prompt', f'  Stream（流式输出，当前：{"ON" if current_bool else "OFF"}） {suffix}: ')],
        style=pt_style,
    ).strip().lower()
    value = current_bool if not answer else answer in ('y', 'yes')
    if value != current_bool:
        state_config['stream'] = value
        changed = True

    # --- Rich rendering ---
    current = state_config.get('rich', DEFAULT_CONFIG['rich'])
    if isinstance(current, str):
        current = current.lower() in ('1', 'true')
    current_bool = bool(current)
    suffix = '[Y/n]' if current_bool else '[y/N]'
    answer = prompt(
        [('class:prompt', f'  Rich（富文本渲染，当前：{"ON" if current_bool else "OFF"}） {suffix}: ')],
        style=pt_style,
    ).strip().lower()
    value = current_bool if not answer else answer in ('y', 'yes')
    if value != current_bool:
        state_config['rich'] = value
        changed = True

    # --- Extra body ---
    current = state_config.get('extra_body')
    current_display = json.dumps(current, ensure_ascii=False) if current else ''
    value = prompt(
        [('class:prompt', f'  Extra body（JSON，可选） [{current_display}]: ' if current_display else '  Extra body（JSON，可选）: ')],
        default=current_display,
        style=pt_style,
    ).strip()
    if value:
        try:
            parsed = json.loads(value)
            state_config['extra_body'] = parsed
            changed = True
        except json.JSONDecodeError:
            console.print('  [yellow]⚠ JSON 格式无效，保持当前值不变。[/yellow]')
    elif current is not None:
        state_config['extra_body'] = None
        changed = True

    console.print()
    return changed


def _chat_loop(ctx: PluginContext):
    store = ctx.state()
    config = store.load()
    if not config:
        config = DEFAULT_CONFIG.copy()
        store.save(config)
    
    service = AIService()
    system_prompt = SYSTEM_PROMPT_RICH if config.get('rich') else SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]

    model = config.get('model', 'unknown')
    rich_on = bool(config.get('rich', True))
    stream_on = bool(config.get('stream', True))

    rich_label = '[green]ON[/green]' if rich_on else '[dim]OFF[/dim]'
    stream_label = '[green]ON[/green]' if stream_on else '[dim]OFF[/dim]'

    sep = '─' * 50
    console.print(f'[cyan]{sep}[/cyan]')
    console.print(
        f'[cyan]Model:[/cyan] [yellow]{model}[/yellow]  '
        f'[cyan]Rich:[/cyan] {rich_label}  '
        f'[cyan]Stream:[/cyan] {stream_label}'
    )
    console.print('[dim]输入 exit 退出 | Ctrl+C 中断[/dim]')
    console.print(f'[cyan]{sep}[/cyan]')


    style = Style.from_dict({'prompt': 'bold green'})

    while True:
        try:
            user_input = prompt([('class:prompt', 'You: ')]).strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[cyan]Chat ended.[/cyan]')
            break

        if user_input.lower() == 'exit':
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        req = ChatRequest(
            messages=messages,
            model=config['model'],
            api_key=config['api_key'],
            api_url=config['api_url'],
            stream=bool(config['stream']),
            extra_body=config.get('extra_body'),
        )

        try:
            if config.get('rich') and getattr(ai_renderer, 'RICH_AVAILABLE', False):
                if req.stream:
                    resp_or_chunks = service.chat(req)
                    reply = ai_renderer.print_streaming_chunks(resp_or_chunks)
                else:
                    status_text = "[bold blue]正在思考...[/bold blue]"
                    with ai_renderer.Status(status_text, spinner="dots"):
                        resp_or_chunks = service.chat(req)
                    reply = extract_assistant_reply(resp_or_chunks)
                    ai_renderer.render_non_streaming_reply(reply)
            else:
                if (not req.stream) and (not config.get('rich')):
                    console.print('[blue]AI:[/blue] 正在思考...', end='')
                resp_or_chunks = service.chat(req)

                if req.stream:
                    reply = _print_streaming_chunks(resp_or_chunks)
                else:
                    reply = extract_assistant_reply(resp_or_chunks)
                    print('\r', end='')
                    console.print(f'[blue]AI:[/blue] {reply}')

            messages.append({"role": "assistant", "content": reply})

        except AIServiceError as e:
            console.print(f'[red]Error: {e}[/red]')
            messages.pop()
        except Exception as e:
            console.print(f'[red]Unknown error: {e}[/red]')
            messages.pop()


@click.command(
    name='ai',
    help='use openai api to chat in terminal',
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--config", "-c",
    is_flag=True,
    default=False,
    help="show config and exit"
)
@click.option(
    '--set', '-S',
    is_flag=True,
    default=False,
    help='interactive configuration setup'
)
def cli(config, set):
    ctx = plugin("pyadd-ai-chat")
    store = ctx.state()
    state_config = store.load()
    if not state_config:
        state_config = DEFAULT_CONFIG.copy()

    # --config: 查看配置
    if config:
        console.print('[bold cyan]AI Configuration:[/bold cyan]')
        for k, v in state_config.items():
            display = v
            if k == 'api_key' and v:
                display = '*' * 12
            elif k == 'extra_body' and v:
                display = json.dumps(v, ensure_ascii=False)
            console.print(f'  [cyan]{k}[/cyan]: [yellow]{display}[/yellow]')
        console.print(f'\n[dim]State file: {store.path}[/dim]')
        return

    # --set: 交互式配置
    if set:
        changed = _interactive_setup(state_config)
        if changed:
            store.save(state_config)
            console.print('[green]✅ 配置已保存。[/green]')
        else:
            console.print('[dim]配置未变更。[/dim]')
        console.print(f'[dim]State file: {store.path}[/dim]\n')
        return

    # api_key 不存在时，自动启动交互式配置
    if not state_config.get('api_key'):
        console.print('[yellow]⚠ API Key 未配置，进入交互式设置...[/yellow]')
        _interactive_setup(state_config)
        store.save(state_config)

        if not state_config.get('api_key'):
            console.print('[red]❌ 未设置 API Key，无法启动聊天。[/red]')
            raise SystemExit(1)

        console.print('[green]✅ 配置已保存，启动聊天...[/green]\n')

    _chat_loop(ctx)