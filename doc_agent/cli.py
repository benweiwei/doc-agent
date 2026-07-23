"""CLI entry point for doc-agent."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Optional

import click
import yaml

from doc_agent import __version__
from doc_agent.config import _find_config_file, load_config


@click.group()
@click.version_option(version=__version__, prog_name="doc-agent")
def main() -> None:
    """Doc-Agent - AI 文档编辑助手"""


@main.command()
@click.option("--port", default=None, type=int, help="服务端口")
@click.option("--host", default=None, help="绑定地址")
@click.option("--no-browser", is_flag=True, help="不自动打开浏览器")
def serve(port: Optional[int], host: Optional[str], no_browser: bool) -> None:
    """启动 Doc-Agent 服务（主入口）"""
    try:
        import uvicorn

        from doc_agent.vcs import VersionControl

        # 1. 加载配置
        cfg = load_config()

        # 2. 用命令行参数覆盖配置
        final_host = host if host is not None else cfg.server.host
        final_port = port if port is not None else cfg.server.port

        # 3. 初始化工作区
        workspace_path = Path(cfg.workspace.path).expanduser()
        vcs = VersionControl(workspace_path)
        vcs.init_workspace()

        click.echo(
            click.style("✓ ", fg="green")
            + f"工作区已就绪: {workspace_path}"
        )
        click.echo(
            click.style("✓ ", fg="green")
            + f"启动服务: http://{final_host}:{final_port}"
        )

        # 5. 自动打开浏览器
        if cfg.server.auto_open_browser and not no_browser:
            url = f"http://{final_host}:{final_port}"

            def _open_browser():
                webbrowser.open(url)

            timer = threading.Timer(0.5, _open_browser)
            timer.daemon = True
            timer.start()

        # 4. 启动 uvicorn 服务
        uvicorn.run(
            "doc_agent.server:app",
            host=final_host,
            port=final_port,
        )
    except Exception as e:
        click.echo(click.style(f"✗ 启动失败: {e}", fg="red"), err=True)
        raise SystemExit(1)


@main.command()
@click.option("--path", default=None, type=click.Path(), help="工作区路径")
def init(path: Optional[str]) -> None:
    """初始化 Doc-Agent 工作区"""
    try:
        from doc_agent.vcs import VersionControl

        # 1. 加载配置
        cfg = load_config()

        # 2. 用参数覆盖工作区路径
        workspace_path = Path(path).resolve() if path else Path(cfg.workspace.path).expanduser()

        # 3. 初始化
        vcs = VersionControl(workspace_path)
        vcs.init_workspace()

        # 4. 打印成功信息
        click.echo(
            click.style("✓ ", fg="green")
            + f"工作区已初始化: {workspace_path}"
        )
    except Exception as e:
        click.echo(click.style(f"✗ 初始化失败: {e}", fg="red"), err=True)
        raise SystemExit(1)


@main.group()
def config() -> None:
    """管理配置"""


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """设置配置项（如 model.provider cloud）"""
    try:
        # 确定配置文件路径
        config_file = _find_config_file()
        if config_file is None:
            # 默认写到当前目录
            config_file = Path.cwd() / "config.yaml"

        # 读取现有配置
        if config_file.is_file():
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        # 设置嵌套键值
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        # 尝试解析值类型
        parsed_value = _parse_value(value)
        current[keys[-1]] = parsed_value

        # 写回配置文件
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        click.echo(
            click.style("✓ ", fg="green")
            + f"已设置 {key} = {parsed_value}"
        )
        click.echo(f"  配置文件: {config_file}")
    except Exception as e:
        click.echo(click.style(f"✗ 设置失败: {e}", fg="red"), err=True)
        raise SystemExit(1)


@config.command("get")
@click.argument("key", required=False)
def config_get(key: Optional[str]) -> None:
    """查看配置（省略key则显示全部）"""
    try:
        cfg = load_config()
        data = cfg.model_dump()

        if key is None:
            # 显示全部
            output = yaml.dump(_sanitize_config(data), default_flow_style=False, allow_unicode=True)
            click.echo(output)
        else:
            # 获取嵌套键
            keys = key.split(".")
            current = data
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    click.echo(click.style(f"✗ 未找到配置项: {key}", fg="yellow"), err=True)
                    raise SystemExit(1)

            if isinstance(current, dict):
                output = yaml.dump(
                    _sanitize_config(current), default_flow_style=False, allow_unicode=True
                )
                click.echo(f"{key}:\n{output}")
            else:
                click.echo(f"{key} = {current}")
    except SystemExit:
        raise
    except Exception as e:
        click.echo(click.style(f"✗ 读取失败: {e}", fg="red"), err=True)
        raise SystemExit(1)


@config.command("show")
def config_show() -> None:
    """显示当前完整配置"""
    try:
        cfg = load_config()
        data = cfg.model_dump()
        sanitized = _sanitize_config(data)
        output = yaml.dump(sanitized, default_flow_style=False, allow_unicode=True)
        click.echo(click.style("当前配置:", fg="cyan", bold=True))
        click.echo(output)
    except Exception as e:
        click.echo(click.style(f"✗ 读取配置失败: {e}", fg="red"), err=True)
        raise SystemExit(1)


# ─── Helpers ─────────────────────────────────────────────────────────────────


_SENSITIVE_KEYS = {"api_key", "api_key_env", "secret", "token", "password"}


def _sanitize_config(data: dict) -> dict:
    """递归脱敏配置中的敏感字段。"""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_config(value)
        elif any(s in key.lower() for s in _SENSITIVE_KEYS):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def _parse_value(value: str):
    """尝试将字符串解析为合适的 Python 类型。"""
    # Bool
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    # Int
    try:
        return int(value)
    except ValueError:
        pass
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    # String
    return value


if __name__ == "__main__":
    main()
