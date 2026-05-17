# mitmproxy 使用总结

## 安装

```bash
# 1. 安装 pyenv（用户目录 Python，避免系统权限问题）
curl -fsSL https://pyenv.run | bash

# 2. 添加到 ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

# 3. 重启终端后安装 Python
pyenv install 3.12.13
pyenv global 3.12.13

# 4. 安装 mitmproxy
pip install mitmproxy -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 运行

```bash
# 终端交互界面
mitmproxy

# Web 图形界面（自动打开浏览器）
mitmweb

# 手机使用需监听所有网卡
mitmweb --listen-host 0.0.0.0
```

## iOS 手机抓包

1. 电脑启动 mitmproxy，手机连同一 Wi-Fi
2. 手机设代理：Wi-Fi 详情 → HTTP 代理 → 手动 → `电脑IP:8080`
3. Safari 打开 `mitm.it` → 下载证书
4. 设置 → 通用 → VPN 与设备管理 → 安装描述文件
5. 设置 → 通用 → 关于本机 → 证书信任设置 → 开启 mitmproxy

## 常用选项

| 选项 | 作用 |
|------|------|
| `-p 8080` | 指定端口 |
| `--mode socks5` | SOCKS5 代理 |
| `--mode transparent` | 透明代理 |
| `--ignore-hosts regex` | 跳过指定域名 |
| `--set block_private=false` | 允许局域网连接 |
| `-w file.flow` | 保存流量 |
| `--scripts script.py` | 加载 Python 脚本 |

## 运行时过滤

| 表达式 | 作用 |
|--------|------|
| `~u keyword` | URL 包含 keyword |
| `~c 200` | 状态码 200 |
| `~m POST` | POST 请求 |
| `!~u .png` | 排除图片 |

## 配置文件

`~/.mitmproxy/config.yaml`
