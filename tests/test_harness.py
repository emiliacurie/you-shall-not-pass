import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import harness as h
from jsonschema import Draft202012Validator


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness-test-')
        self.base = Path(self.temp.name)
        self.repo = self.base/'repo'
        self.remote = self.base/'remote.git'
        self.env = os.environ.copy()
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0', PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'])
        self.repo.mkdir()
        self.git('init', '-q', '--initial-branch=main')
        self.git('config','user.name','Harness Test'); self.git('config','user.email','harness@example.invalid')
        (self.repo/'readme.txt').write_text('Initial\n')
        self.git('add','readme.txt'); self.git('commit','-qm','Initial')
        subprocess.run(['git','init','-q','--bare','--initial-branch=main',str(self.remote)],env=self.env,check=True)
        self.git('remote','add','origin',str(self.remote)); self.git('push','-q','origin','main')
        self.git('symbolic-ref','refs/remotes/origin/HEAD','refs/remotes/origin/main')
        self.git('switch','-qc','feature/test')
        self.policy = h.load_policy()

    def tearDown(self):
        self.temp.cleanup()

    def git(self,*args,check=True):
        p=subprocess.run(['git','-C',str(self.repo),*args],env=self.env,capture_output=True,text=True)
        if check and p.returncode: self.fail(p.stderr)
        return p

    def classify(self,command):
        old = os.environ.copy()
        try:
            os.environ.update(self.env)
            return h.command_check(command,str(self.repo),self.policy)
        finally:
            os.environ.clear(); os.environ.update(old)

    def payload(self,command):
        return {'cwd':str(self.repo),'tool_name':'Bash','tool_input':{'command':command}}

    def hook(self,host,payload):
        return subprocess.run([sys.executable,str(ROOT/'scripts/harness.py'),'hook','--host',host],input=json.dumps(payload),env=self.env,capture_output=True,text=True)

    def approval_policy(self):
        policy=copy.deepcopy(self.policy)
        policy['actions'].update(discard_unsaved_work='require_scoped_approval',rewrite_history='require_scoped_approval')
        return policy

    def test_command_fixtures(self):
        cases=json.loads((ROOT/'tests/cases.json').read_text())
        schema=json.loads((ROOT/'tests/cases.schema.json').read_text())
        Draft202012Validator(schema).validate(cases)
        self.policy=self.approval_policy()
        for c in cases:
            with self.subTest(c['id']):
                self.git('switch','-q',c['branch'])
                self.assertEqual(self.classify(c['command'])['decision'],c['expected'])

    def test_default_branch_not_named_main(self):
        self.git('branch','trunk')
        self.git('symbolic-ref','refs/remotes/origin/HEAD','refs/remotes/origin/trunk')
        self.assertEqual(self.classify('git push origin feature/test:trunk')['decision'],'deny')
        self.git('switch','-q','trunk')
        self.assertEqual(self.classify('git commit -m update')['decision'],'deny')

    def test_missing_remote_head_blocks_mutation(self):
        self.git('symbolic-ref','--delete','refs/remotes/origin/HEAD')
        with self.assertRaises(h.GuardError): self.classify('git commit -m update')
        self.assertEqual(self.classify('git status')['decision'],'allow')

    def test_actual_directory_for_git_C(self):
        self.git('switch','-q','main')
        cmd='git -C '+str(self.repo)+' commit -m update'
        self.assertEqual(h.command_check(cmd,str(self.base),self.policy)['decision'],'deny')

    def test_file_edit_checks_target_repository(self):
        self.git('switch','-q','main')
        payload={'cwd':str(self.base),'tool_name':'Write','tool_input':{'file_path':str(self.repo/'new.txt'),'content':'hello'}}
        self.assertEqual(h.tool_check(payload,self.policy)['decision'],'deny')

    def test_apply_patch_checks_target(self):
        self.git('switch','-q','main')
        payload={'cwd':str(self.repo),'tool_name':'apply_patch','tool_input':{'command':'*** Begin Patch\n*** Update File: readme.txt\n@@\n-Initial\n+Hello\n*** End Patch'}}
        self.assertEqual(h.tool_check(payload,self.policy)['decision'],'deny')
        self.git('switch','-q','feature/test')
        self.assertEqual(h.tool_check(payload,self.policy)['decision'],'allow')

    def test_adapter_decisions_and_no_blanket_allow(self):
        for host in ['claude','codex']:
            safe=self.hook(host,self.payload('git status'))
            self.assertEqual(safe.returncode,0); self.assertEqual(json.loads(safe.stdout),{})
            unsafe=self.hook(host,self.payload('git push origin main'))
            self.assertEqual(json.loads(unsafe.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
            discard=self.hook(host,self.payload('git restore -- readme.txt'))
            self.assertEqual(json.loads(discard.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

    def test_default_policy_denies_loss_of_work(self):
        self.git('switch','-q','feature/test')
        for cmd in ['git restore -- readme.txt','git reset --hard','git rebase main']:
            with self.subTest(cmd):
                self.assertEqual(self.classify(cmd)['decision'],'deny')

    def test_approval_policy_still_asks_in_claude(self):
        package=self.base/'approval-package'; (package/'scripts').mkdir(parents=True)
        shutil.copy2(ROOT/'scripts/harness.py',package/'scripts/harness.py')
        shutil.copy2(ROOT/'policy.schema.json',package/'policy.schema.json')
        (package/'policy.json').write_text(json.dumps(self.approval_policy()))
        for host,expected in [('claude','ask'),('codex','deny')]:
            p=subprocess.run([sys.executable,str(package/'scripts/harness.py'),'hook','--host',host],input=json.dumps(self.payload('git restore -- readme.txt')),env=self.env,capture_output=True,text=True)
            self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],expected)

    def test_malformed_payload_fails_without_echoing_input(self):
        for host in ['claude','codex']:
            p=self.hook(host,{'tool_input':'SENSITIVE_TEST_MARKER'})
            self.assertNotIn('SENSITIVE_TEST_MARKER',p.stdout+p.stderr)
            self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
        p=subprocess.run([sys.executable,str(ROOT/'scripts/harness.py'),'hook','--host','codex'],input='{bad-json SENSITIVE_TEST_MARKER',env=self.env,capture_output=True,text=True)
        self.assertEqual(p.returncode,2); self.assertNotIn('SENSITIVE_TEST_MARKER',p.stdout+p.stderr)

    def test_schema_rejects_unknown_fields_and_invalid_choices(self):
        validator=Draft202012Validator(json.loads((ROOT/'policy.schema.json').read_text()))
        for mutate in [lambda p:p.update(surprise=True),lambda p:p['actions'].update(force_push='ask'),lambda p:p.update(version=2),lambda p:p['protected_branches'].update(additional=[]),lambda p:p['actions'].pop('force_push')]:
            p=copy.deepcopy(self.policy); mutate(p)
            self.assertTrue(list(validator.iter_errors(p)))

    def test_policy_allow_cannot_bypass_other_deny(self):
        self.policy['actions']['force_push']='allow'
        self.assertEqual(self.classify('git push --force origin main')['decision'],'deny')
        self.policy['actions']['skip_checks']='allow'
        self.git('switch','-q','main')
        self.assertEqual(self.classify('git commit --no-verify -m update')['decision'],'deny')

    def test_amend_cannot_approve_a_secret(self):
        (self.repo/'.env').write_text('KEY=local\n'); self.git('add','.env')
        self.assertEqual(self.classify('git commit --amend -m update')['decision'],'deny')

    def test_staged_filename_with_leading_space(self):
        self.enable_git_hooks()
        (self.repo/' safe.txt').write_text('Hello\n'); self.git('add',' safe.txt')
        self.git('commit','-qm','Space in filename')

    def test_fetch_configuration_cannot_target_main(self):
        self.git('config','remote.origin.fetch','+refs/heads/main:refs/heads/main')
        self.assertEqual(self.classify('git fetch origin')['decision'],'deny')

    def test_exec_workdir_is_honored(self):
        self.git('switch','-q','main')
        payload={'cwd':str(self.base),'tool_name':'exec_command','tool_input':{'cmd':'git commit -m test','workdir':str(self.repo)}}
        self.assertEqual(h.tool_check(payload,self.policy)['decision'],'deny')

    def test_invalid_policy_blocks_hook_runtime(self):
        package=self.base/'invalid-package'; (package/'scripts').mkdir(parents=True)
        shutil.copy2(ROOT/'scripts/harness.py',package/'scripts/harness.py')
        shutil.copy2(ROOT/'policy.schema.json',package/'policy.schema.json')
        invalid=copy.deepcopy(self.policy); invalid['actions']['force_push']='SENSITIVE_TEST_MARKER'
        (package/'policy.json').write_text(json.dumps(invalid))
        p=subprocess.run([sys.executable,str(package/'scripts/harness.py'),'hook','--host','codex'],input=json.dumps(self.payload('git status')),env=self.env,capture_output=True,text=True)
        self.assertEqual(p.returncode,2); self.assertNotIn('SENSITIVE_TEST_MARKER',p.stdout+p.stderr)

    def test_installer_requires_explicit_scope(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/install.py')],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(self.git('config','--get','core.hooksPath',check=False).returncode,1)

    def test_installer_preserves_existing_configuration(self):
        self.git('config','core.hooksPath','existing-hooks')
        destination=self.base/'installation'
        p=subprocess.run([sys.executable,str(ROOT/'scripts/install.py'),'--repo',str(self.repo),'--destination',str(destination)],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0); self.assertFalse(destination.exists())
        self.assertEqual(self.git('config','--get','core.hooksPath').stdout.strip(),'existing-hooks')

    def enable_git_hooks(self):
        self.git('config','core.hooksPath',str(ROOT/'scripts/git-hooks'))

    def test_real_commit_allowed_on_feature(self):
        self.enable_git_hooks()
        (self.repo/'readme.txt').write_text('Changed\n'); self.git('add','readme.txt')
        self.git('commit','-qm','Safe change')
        self.assertEqual(self.git('status','--porcelain').stdout,'')

    def test_real_commit_blocked_on_main(self):
        self.git('switch','-q','main'); self.enable_git_hooks()
        before=self.git('rev-parse','HEAD').stdout
        (self.repo/'readme.txt').write_text('Changed\n'); self.git('add','readme.txt')
        p=self.git('commit','-qm','Blocked',check=False)
        self.assertNotEqual(p.returncode,0); self.assertEqual(self.git('rev-parse','HEAD').stdout,before)

    def test_staged_secret_in_source_even_if_worktree_cleaned(self):
        self.enable_git_hooks()
        fake='ghp_'+'A'*36
        (self.repo/'app.py').write_text('token = "'+fake+'"\n'); self.git('add','app.py')
        (self.repo/'app.py').write_text('token = ""\n')
        p=self.git('commit','-qm','Blocked',check=False)
        self.assertNotEqual(p.returncode,0); self.assertNotIn(fake,p.stdout+p.stderr)

    def test_env_staged_blocked(self):
        self.enable_git_hooks()
        (self.repo/'.env').write_text('EMPTY=\n'); self.git('add','.env')
        self.assertNotEqual(self.git('commit','-qm','Blocked',check=False).returncode,0)

    def test_placeholder_values_are_not_secrets(self):
        self.assertFalse(h.detected_secret('PAYMENTS_API_KEY=your_payments_api_key\nDATABASE_PASSWORD=your_database_password\nAUTH_TOKEN=xxxx\n'))
        self.assertTrue(h.detected_secret('DATABASE_'+'PASSWORD'+'=not_a_real_test_password\n'))
        self.assertTrue(h.detected_secret('API'+'_KEY'+'=yourcompany_8f2k1x9q\n'))

    def test_example_not_automatically_safe(self):
        self.enable_git_hooks()
        (self.repo/'.env.example').write_text('DATABASE_'+'PASSWORD'+'=not_a_real_test_password\n'); self.git('add','.env.example')
        self.assertNotEqual(self.git('commit','-qm','Blocked',check=False).returncode,0)
        (self.repo/'.env.example').write_text('DATABASE_'+'PASSWORD'+'=\n'+'API'+'_KEY'+'=\n'); self.git('add','.env.example')
        self.git('commit','-qm','Safe template')

    def test_real_push_feature_allowed_main_blocked(self):
        (self.repo/'readme.txt').write_text('Changed\n'); self.git('add','readme.txt'); self.git('commit','-qm','Feature')
        self.enable_git_hooks()
        self.git('push','-q','origin','feature/test')
        before=subprocess.check_output(['git','--git-dir',str(self.remote),'rev-parse','main'],env=self.env)
        self.assertNotEqual(self.git('push','origin','HEAD:main',check=False).returncode,0)
        self.assertEqual(subprocess.check_output(['git','--git-dir',str(self.remote),'rev-parse','main'],env=self.env),before)

    def test_real_force_push_blocked(self):
        self.git('push','-q','origin','feature/test')
        (self.repo/'readme.txt').write_text('New\n'); self.git('add','readme.txt'); self.git('commit','-qm','New'); self.git('push','-q','origin','feature/test')
        self.git('reset','--hard','HEAD~1'); self.enable_git_hooks()
        self.assertNotEqual(self.git('push','--force','origin','feature/test',check=False).returncode,0)

    def test_real_remote_delete_blocked(self):
        self.git('push','-q','origin','feature/test'); self.enable_git_hooks()
        self.assertNotEqual(self.git('push','origin',':feature/test',check=False).returncode,0)

    def test_existing_repo_hook_still_runs(self):
        hook=self.repo/'.git/hooks/pre-commit'; hook.write_text('#!/bin/sh\nexit 42\n'); hook.chmod(0o755)
        self.enable_git_hooks()
        (self.repo/'readme.txt').write_text('Changed\n'); self.git('add','readme.txt')
        self.assertNotEqual(self.git('commit','-qm','Blocked by existing hook',check=False).returncode,0)


if __name__=='__main__':
    unittest.main(verbosity=2)
