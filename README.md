# Windows Administrator 批量重命名脚本

这个仓库提供了一个 Python 脚本，可通过 WinRM 批量连接 Windows 服务器，并把**内置管理员账户**（SID 结尾为 `-500`）从 `Administrator` 重命名为 `invadmin`。

## 依赖

```bash
pip install pywinrm
```

## 准备目标列表

新建 `servers.txt`，每行一个主机名、IP 或完整 WinRM 地址，例如：

```text
10.0.0.10
server01.contoso.local
https://server02.contoso.local:5986
```

## 使用示例

### 1. 先做预检查（不实际重命名）

```bash
python batch_rename_administrator.py \
  --targets servers.txt \
  --username domain\\opsuser \
  --transport ntlm \
  --dry-run
```

### 2. 实际执行重命名

```bash
python batch_rename_administrator.py \
  --targets servers.txt \
  --username domain\\opsuser \
  --transport ntlm
```

脚本会提示输入密码，也可以通过 `--password` 直接传入。

## 常用参数

- `--new-name`：目标用户名，默认是 `invadmin`。
- `--https`：未在目标列表中写协议时，默认改用 HTTPS WinRM。
- `--port`：指定 WinRM 端口。
- `--skip-cert-validation`：跳过 HTTPS 证书校验。
- `--dry-run`：只检查，不执行重命名。
- `--workers`：并发连接的线程数，默认 `5`。

## 实现说明

- 脚本不会仅凭名字查找 `Administrator`，而是会定位 **SID 结尾为 `-500` 的本地内置管理员账户**，避免因系统语言不同或该账号已被改名而找错对象。
- 如果目标主机上 `invadmin` 已存在，脚本会报错并跳过该主机。
- 返回值为：全部成功时退出码 `0`，存在失败时退出码 `1`。
