import subprocess
import tempfile

from django.http import HttpResponse
from django.conf import settings

def print_to_pdf(request, name, url):
    # Build the url manually to obtain GET parameters without having to
    # append request.META['QUERY_STRING'].
    url = '/'.join(request.build_absolute_uri().split('/')[5:])
    if not url.startswith('/'):
        url = '/' + url
    url = request.build_absolute_uri(url)
    session_id = request.COOKIES.get('sessionid', '')
    with tempfile.NamedTemporaryFile(dir='/tmp/') as temp:
        command = [
            'env', '-i',
            # If you are use the wkhtmltopdf 0.9.9 package on Ubuntu,
            # then it will require an X server, so if you want to run it
            # headless on a server, use xvfb-run.
            #'xvfb-run', '-a',
            settings.WKHTMLTOPDF_PATH, '--quiet', '--disable-javascript',
            '--page-size', 'Letter', '--cookie', 'sessionid', session_id,
            url, temp.name
        ]
        print '\n', command
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        p.wait()
        response = HttpResponse(temp.read(), mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename={}.pdf'.format(name)
    return response
