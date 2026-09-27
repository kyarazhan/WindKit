"""发布到 GitHub：创建 Release 并上传 release/<版本>/ 的产物。

前置：代码已 push、tag 已推（git push origin main v<版本>）。
用法:
    python tools/publish_release.py 1.0.1
上传内容（release/<版本>/ 下存在的）：
    versions.json（必传）、WindKit-<版本>.zip（全量）、<旧>-<新>-patch.zip（增量）
凭据：git credential manager 里已存的 GitHub 令牌（与 push 同源，不落盘）。
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = 'kyarazhan/WindKit'
GIT = r'C:\Users\52736\Documents\Project\.tools\PortableGit\cmd\git.exe'

API = 'https://api.github.com'
UP = 'https://uploads.github.com'


def gh_token() -> str:
    fill = subprocess.run([GIT, 'credential', 'fill'],
                          input='protocol=https\nhost=github.com\n',
                          capture_output=True, text=True, timeout=30)
    for line in fill.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1].strip()
    sys.exit('未取到 GitHub 凭据（git credential manager）')


def req(url, token, data=None, headers=None, method='GET'):
    h = {'Authorization': f'Bearer {token}',
         'User-Agent': 'WindKit-Release',
         'Accept': 'application/vnd.github+json'}
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    return urllib.request.urlopen(r, timeout=300)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    version = sys.argv[1].lstrip('v')
    tag = f'v{version}'
    reldir = os.path.join(ROOT, 'release', version)
    if not os.path.isdir(reldir):
        sys.exit(f'缺目录: {reldir}（先跑 tools/release.py {version}）')

    token = gh_token()

    files = sorted(os.listdir(reldir))
    notes = [l for l in files if l == 'versions.json']
    if not notes:
        sys.exit('缺 versions.json')
    idx = json.load(open(os.path.join(reldir, 'versions.json'),
                         encoding='utf-8'))
    entry = next((e for e in idx['versions'] if e['version'] == version), {})
    changelog = entry.get('changelog', '')

    payload = json.dumps({'tag_name': tag, 'name': f'WindKit {tag}',
                          'body': f'## WindKit {tag}\n\n{changelog}\n\n'
                                  '### 安装\n- 新用户：下载 '
                                  f'`WindKit-{version}.zip` 解压即用\n'
                                  '- 老用户：更新器「检查更新」自动升级，'
                                  '或下载增量包本地安装\n',
                          'draft': False, 'prerelease': False}).encode()
    try:
        with req(f'{API}/repos/{REPO}/releases', token, payload,
                 {'Content-Type': 'application/json'}, 'POST') as r:
            rel = json.load(r)
        print('release created:', rel['html_url'])
    except urllib.error.HTTPError as e:
        if e.code == 422:
            with req(f'{API}/repos/{REPO}/releases/tags/{tag}', token) as r:
                rel = json.load(r)
            print('release exists:', rel['html_url'])
        else:
            sys.exit(f'create failed: {e.code} {e.read()[:300]}')

    rid = rel['id']
    existing = {a['name'] for a in rel.get('assets', [])}
    for name in files:
        path = os.path.join(reldir, name)
        if not os.path.isfile(path):
            continue
        ctype = 'application/json' if name.endswith('.json') \
            else 'application/zip'
        if name in existing:
            for a in rel['assets']:
                if a['name'] == name:
                    with req(f"{API}/repos/{REPO}/releases/assets/{a['id']}",
                             token, method='DELETE'):
                        pass
                    print('replaced old asset:', name)
                    break
        size = os.path.getsize(path)
        t0 = time.time()
        with open(path, 'rb') as f:
            blob = f.read()
        with req(f'{UP}/repos/{REPO}/releases/{rid}/assets?name={name}',
                 token, blob, {'Content-Type': ctype}, 'POST') as r:
            info = json.load(r)
        del blob
        print(f'uploaded: {name} {size/1048576:.1f}MB '
              f'({time.time()-t0:.0f}s) state={info.get("state")}')

    print('\n完成:', rel['html_url'])


if __name__ == '__main__':
    main()
