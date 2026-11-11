import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from flask_login import LoginManager, login_user
from app.admin import admin_bp, GROUPS, revision, update_text, create_admin_link
from urllib.parse import urlsplit
from app.repos.users_repo import User
from dotenv import dotenv_values

class AdminTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.env=Path(self.tmp.name)/'.env'; self.conf=Path(self.tmp.name)/'config.conf'
  self.env.write_text('PAYOS_API_KEY=keep-secret\nUNRELATED=preserved\n'); self.conf.write_text('POLL_INTERVAL_SECONDS=600\n')
  self.p=patch.dict(os.environ,ENV_FILE=str(self.env),CONF_FILE=str(self.conf),MANAGED_RESTART='0'); self.p.start(); self.addCleanup(self.p.stop)
  self.app=Flask(__name__,template_folder=str(Path('app/templates').resolve())); self.app.config.update(SECRET_KEY='test',ADMIN_TELEGRAM_USER_ID='123',WTF_CSRF_ENABLED=False,TESTING=True)
  lm=LoginManager(self.app); self.user=User('u','owner','hash',{'telegramChatId':'123'},False,None,'123'); lm.user_loader(lambda _:self.user)
  self.app.register_blueprint(admin_bp,url_prefix='/admin'); self.client=self.app.test_client()
 def login(self):
  with self.client.session_transaction() as s:s['_user_id']='u';s['_fresh']=True
 def payload(self):
  d={'revision':revision({'.env':self.env.read_text(),'config.conf':self.conf.read_text()})}
  for _,_,_,fields in GROUPS:
   for key,_,kind in fields:d[key]='600' if kind=='int' else 'on' if kind=='bool' else ''
  return d
 def test_denies_spoofed_id(self):
  self.login();self.user.telegram_verified_id=None
  self.assertEqual(self.client.get('/admin/').status_code,403)
 def test_verify_accepts_copied_trailing_slash_and_consumes_token(self):
  self.login();self.user.telegram_verified_id=None
  self.app.config['WEBSITE_URL']='http://localhost'
  link=urlsplit(create_admin_link(self.app,'123'))
  path=link.path+'?'+link.query+'/'
  with patch('app.admin.get_db') as db:
   response=self.client.post(path)
   self.assertEqual(response.status_code,302)
   db.return_value.collection.return_value.document.return_value.update.assert_called_once_with({'telegramVerifiedId':'123'})
   self.assertEqual(self.client.post(path).status_code,403)
 def test_verify_rejects_wrong_account(self):
  self.login();self.app.config['WEBSITE_URL']='http://localhost'
  link=urlsplit(create_admin_link(self.app,'123'))
  self.user.settings['telegramChatId']='456'
  with patch('app.admin.get_db') as db:
   self.assertEqual(self.client.post(link.path+'?'+link.query).status_code,403)
   db.assert_not_called()
 def test_admin_page_hides_secrets(self):
  self.login();self.app.config['PAYOS_API_KEY']='keep-secret'
  r=self.client.get('/admin/');self.assertEqual(r.status_code,200);self.assertNotIn(b'keep-secret',r.data)
 def test_save_preserves_secret_and_unrelated(self):
  self.login();r=self.client.post('/admin/',data=self.payload());self.assertEqual(r.status_code,200)
  self.assertEqual(dotenv_values(self.env)['PAYOS_API_KEY'],'keep-secret');self.assertEqual(dotenv_values(self.env)['UNRELATED'],'preserved');self.assertEqual(dotenv_values(self.conf)['SCHEDULER_ENABLED'],'true')
 def test_stale_submission_does_not_write(self):
  self.login();d=self.payload();d['revision']='stale';before=self.env.read_text();self.client.post('/admin/',data=d);self.assertEqual(before,self.env.read_text())
 def test_invalid_interval_does_not_write(self):
  self.login();d=self.payload();d['POLL_INTERVAL_SECONDS']='0';before=self.conf.read_text();self.client.post('/admin/',data=d);self.assertEqual(before,self.conf.read_text())
 def test_csrf_required(self):
  self.login();self.app.config['WTF_CSRF_ENABLED']=True;before=self.env.read_text();self.client.post('/admin/',data=self.payload());self.assertEqual(before,self.env.read_text())
 def test_roundtrip_quote(self):
  self.env.write_text(update_text('',{'KEY':"a'b\\c"}));self.assertEqual(dotenv_values(self.env)['KEY'],"a'b\\c")
class FeatureTests(unittest.TestCase):
 def test_removed_routes_and_templates(self):
  from app import create_app
  with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
   app=create_app()
  client=app.test_client()
  for path in ['/settings/oil','/settings/power-outage']:
   self.assertEqual(client.get(path).status_code,404)
  self.assertEqual(client.get('/').status_code,200)
  for name in app.jinja_env.list_templates():
   app.jinja_env.get_template(name)
 def test_tracking_off_does_not_call_repository(self):
  from app.tracking.services import TrackingService
  app=Flask(__name__); app.config['TRACKING_ENABLED']=False
  with app.app_context(), patch('app.tracking.services.TrackingsRepo.get_by_id') as repo:
   self.assertFalse(TrackingService.refresh_tracking('x'));repo.assert_not_called()
 def test_providers_disabled(self):
  from app.notifications.registry import registry,init_notification_providers
  from app.payments.registry import registry as payments,init_gateways
  app=Flask(__name__);app.config.update(TELEGRAM_ENABLED=False,ZALO_ENABLED=False,PAYOS_ENABLED=False,TELEGRAM_BOT_TOKEN='fake',ZALO_BOT_TOKEN='fake')
  init_notification_providers(app);init_gateways(app)
  self.assertEqual(registry.list_providers(),[]);self.assertEqual(payments.list_gateways(),[])
if __name__=='__main__':unittest.main()
