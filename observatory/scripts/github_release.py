"""Publishing helper using the existing GitHub Git credential, never logging tokens."""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
import zipfile
import io
from pathlib import Path

REPO='KyleNeumeier/observatory'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['fork','status','release','runs','jobs','logs']);parser.add_argument('--run-id');args=parser.parse_args()
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\nusername=KyleNeumeier\n\n',text=True,capture_output=True,check=True)
    credential=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    token=credential['password']
    def api(path,method='GET',body=None,upload=None):
        url=path if path.startswith('https://uploads.github.com/') else 'https://api.github.com'+path
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ObservatoryPortfolio'}
        data=None
        if upload:
            data=Path(upload).read_bytes();headers['Content-Type']='application/zip'
        elif body is not None:
            data=json.dumps(body).encode();headers['Content-Type']='application/json'
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code==404:return None
            raise RuntimeError(f'GitHub {method} failed with HTTP {e.code}') from None
    if args.action=='fork':
        existing=api('/repos/'+REPO)
        if existing:
            if existing.get('parent',{}).get('full_name')!='bilawalsidhu/gods-eye-view':
                raise RuntimeError('Existing observatory is not the expected fork; refusing to modify it')
            print(json.dumps({'url':existing['html_url'],'reused':True}))
        else:
            r=api('/repos/bilawalsidhu/gods-eye-view/forks','POST',{'name':'observatory','default_branch_only':True})
            print(json.dumps({'url':r['html_url'],'created':True}))
    elif args.action=='status':
        r=api('/repos/'+REPO)
        print(json.dumps({'url':r['html_url'],'branch':r['default_branch'],'fork':r['fork']}))
    elif args.action=='runs':
        r=api('/repos/'+REPO+'/actions/workflows/observatory.yml/runs?per_page=3')
        print(json.dumps([{'id':x['id'],'status':x['status'],'conclusion':x['conclusion'],'url':x['html_url']} for x in (r or {}).get('workflow_runs',[])]))
    elif args.action=='jobs':
        if not args.run_id or not args.run_id.isdigit():raise RuntimeError('--run-id is required')
        r=api(f'/repos/{REPO}/actions/runs/{args.run_id}/jobs')
        print(json.dumps([{'name':j['name'],'conclusion':j['conclusion'],'url':j['html_url'],
                          'steps':[{'name':s['name'],'conclusion':s['conclusion'],'number':s['number']} for s in j['steps']]}
                          for j in (r or {}).get('jobs',[])]))
    elif args.action=='logs':
        if not args.run_id or not args.run_id.isdigit():raise RuntimeError('--run-id is required')
        req=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/runs/{args.run_id}/logs',
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ObservatoryPortfolio'})
        with urllib.request.urlopen(req,timeout=120) as response:data=response.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            text='\n'.join(z.read(name).decode('utf-8','replace') for name in z.namelist())
        lines=[line for line in text.splitlines() if '##[error]' in line or 'FAILED' in line or 'ERROR' in line or 'AssertionError' in line]
        print('\n'.join(lines[-100:]))
    elif args.action=='release':
        r=api('/repos/'+REPO+'/releases/tags/v0.1.0')
        if not r:
            r=api('/repos/'+REPO+'/releases','POST',{'tag_name':'v0.1.0','name':'Observatory 0.1 — frozen earthquake investigation demo','body':'Original earthquake analytics built on God’s Eye View. Includes 2021–2025 experiment outputs and frozen public-source inputs. See README and observatory/docs for methodology, attribution, setup, and validation limitations.','draft':False,'prerelease':True})
        if not any(a['name']=='frozen-inputs.zip' for a in r.get('assets',[])):
            api(r['upload_url'].split('{')[0]+'?name=frozen-inputs.zip','POST',upload='observatory/output/frozen-inputs.zip')
        print(json.dumps({'release':r['html_url']}))


if __name__=='__main__':main()
