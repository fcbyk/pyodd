import click
import tkinter as tk
import random

def create_popup(root, title, tips, screen_width, screen_height):
    # 随机窗口位置(确保窗口完全显示在屏幕内)
    window_width = 250
    window_height = 60
    x = random.randrange(0, screen_width - window_width)
    y = random.randrange(0, screen_height - window_height)

    # 使用 Toplevel 创建子窗口
    window = tk.Toplevel(root)
    window.title(title)
    window.geometry(f"{window_width}x{window_height}+{x}+{y}")

    tip = random.choice(tips)

    # 多样的背景颜色
    bg_colors = [
        'lightpink', 'skyblue', 'lightgreen', 'lavender',
        'lightyellow', 'plum', 'coral', 'bisque', 'aquamarine',
        'mistyrose', 'honeydew', 'lavenderblush', 'oldlace'
    ]
    bg = random.choice(bg_colors)

    # 创建标签并显示文字
    tk.Label(
        window,
        text=tip,
        bg=bg,
        font=('微软雅黑', 16),
        width=30,
        height=3
    ).pack()

    # 窗口置顶显示
    window.attributes('-topmost', True)

@click.command(name='popup', help='Display multiple popup windows with random tips at random screen positions')
@click.option('--title', '-t', default='温馨提示', help='Title text for the popup windows')
@click.option('--numbers', '-n', default=20, type=int, help='Number of popup windows to display (default: 20, max recommended: 50)')
@click.argument('tips', nargs=-1)
def popup(title,numbers,tips):
    if not tips:
        tips = ['多喝水哦~', '保持微笑呀', '每天都要元气满满',
        '记得吃水果', '保持好心情', '好好爱自己', '我想你了',
        '梦想成真', '期待下一次见面', '金榜题名',
        '顺顺利利', '早点休息', '愿所有烦恼都消失',
        '别熬夜', '今天过得开心嘛', '天冷了，多穿衣服']

    # 验证参数
    if numbers < 1:
        click.echo("Number of popups must be greater than 0")
        return
        
    if numbers > 50:
        click.echo(f"Warning: Will create {numbers} windows, this may affect performance!")
        if not click.confirm('Do you want to continue?'):
            return

    # 创建隐藏的根窗口（所有操作在主线程执行）
    root = tk.Tk()
    root.withdraw()  # 隐藏根窗口

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    created = 0

    def schedule_next():
        nonlocal created
        if created < numbers:
            create_popup(root, title, tips, screen_width, screen_height)
            created += 1
            # 每隔 5ms 创建下一个窗口
            root.after(5, schedule_next)

    # 启动定时器，在主线程中分批创建窗口
    root.after(0, schedule_next)
    root.mainloop()


if __name__ == '__main__':
    popup()