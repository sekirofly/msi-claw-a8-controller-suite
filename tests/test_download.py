import io
import json
import unittest
import urllib.error
from unittest.mock import patch
import installer


class DownloadTests(unittest.TestCase):
    def error(self):
        return urllib.error.HTTPError('https://github.com/file', 504, 'Gateway timeout', {}, None)

    def test_transient_error_retries(self):
        with patch.object(installer.urllib.request, 'urlopen', side_effect=[self.error(), io.BytesIO(b'zip')]) as request, patch.object(installer.time, 'sleep'):
            self.assertEqual(installer.read_url('https://github.com/file', 100), b'zip')
        self.assertEqual(request.call_count, 2)

    def metadata(self):
        return {'tag_name':'v'+installer.VERSION,'draft':False,'assets':[
            {'name':installer.FOLDER+'.zip','id':123,'size':3,'state':'uploaded'}]}

    def test_official_api_fallback(self):
        url=installer.REPO+'/releases/download/v'+installer.VERSION+'/'+installer.FOLDER+'.zip'
        with patch.object(installer, 'read_url', side_effect=[self.error(),json.dumps(self.metadata()).encode(),b'zip']) as read:
            self.assertEqual(installer.fetch(url), b'zip')
        self.assertEqual(read.call_args.args, ('https://api.github.com/repos/sekirofly/msi-claw-a8-controller-suite/releases/assets/123',16*1024*1024,'application/octet-stream'))

    def test_reject_wrong_release_or_asset(self):
        url=installer.REPO+'/releases/download/v'+installer.VERSION+'/'+installer.FOLDER+'.zip'
        for change in ('tag','size','duplicate'):
            meta=self.metadata()
            if change=='tag':meta['tag_name']='v0.0.0'
            if change=='size':meta['assets'][0]['size']=17*1024*1024
            if change=='duplicate':meta['assets']*=2
            with self.subTest(change=change), patch.object(installer,'read_url',side_effect=[self.error(),json.dumps(meta).encode()]) as read:
                with self.assertRaises(ValueError):installer.fetch(url)
                self.assertEqual(read.call_count,2)

    def test_oversized_response_never_falls_back(self):
        with patch.object(installer.urllib.request,'urlopen',return_value=io.BytesIO(b'1234')):
            with self.assertRaisesRegex(ValueError,'size limit'):installer.fetch('https://github.com/file',3)

    def test_unrelated_url_never_uses_release_api(self):
        with patch.object(installer,'read_url',side_effect=self.error()) as read:
            with self.assertRaises(urllib.error.HTTPError):installer.fetch('https://example.com/file')
        self.assertEqual(read.call_count,1)
