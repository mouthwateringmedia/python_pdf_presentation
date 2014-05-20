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
            '--print-media-type',
            url, temp.name
        ]
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        p.wait()
        response = HttpResponse(temp.read(), mimetype='application/pdf')
    response['Content-Disposition'] = 'inline; filename={}.pdf'.format(name)
    return response


from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse


def pdf_header(request):
    return render_to_response(
        'pdf_header.html',
        dict(request=request)
    )


def print_to_pdf_with_headers(request, name, url):
    # Build the url manually to obtain GET parameters without having to
    # append request.META['QUERY_STRING'].
    url = '/'.join(request.build_absolute_uri().split('/')[5:])
    if not url.startswith('/'):
        url = '/' + url
    url = request.build_absolute_uri(url)
    session_id = request.COOKIES.get('sessionid', '')
    with tempfile.NamedTemporaryFile(dir='/tmp/') as temp:
        header_url = 'http://localhost:8000' + reverse('pdf_header')
        command = [
            'env', '-i',
            # If you are use the wkhtmltopdf 0.9.9 package on Ubuntu,
            # then it will require an X server, so if you want to run it
            # headless on a server, use xvfb-run.
            #'xvfb-run', '-a',
            settings.WKHTMLTOPDF_PATH, '--quiet', '--disable-javascript',
            '--page-size', 'Letter', '--cookie', 'sessionid', session_id,
            '--print-media-type',
            '--header-html', header_url,
            #'--footer-html', footer_url,
            url, temp.name
        ]
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        p.wait()
        response = HttpResponse(temp.read(), mimetype='application/pdf')
    response['Content-Disposition'] = 'inline; filename={}.pdf'.format(name)
    return response


import os
from cStringIO import StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfFileWriter, PdfFileReader


def _get_header_pdf(height, text):
    packet = StringIO()
    c = canvas.Canvas(packet, pagesize=(letter[0], height))
    c.setFont('Courier-Bold', 9)
    c.setFillColorRGB(1, 0, 0)
    c.drawString(40, int(height) - 10, text)
    c.showPage()
    c.save()
    packet.seek(0)
    return PdfFileReader(packet)


def add_header(request, custom_text):
    sample1 = open(os.path.join(settings.BASE_DIR, 'static/sample1.pdf'))
    sample2 = open(os.path.join(settings.BASE_DIR, 'static/sample2.pdf'))
    pdf_writer = PdfFileWriter()
    for file_obj in (sample1, sample2):
        pdf_reader = PdfFileReader(file_obj)
        for i in range(pdf_reader.getNumPages()):
            page = pdf_reader.getPage(i)
            header_text = '%s      %s       Page %d of %d' % (
                custom_text,
                file_obj.name.split('/')[-1],
                i+1,
                pdf_reader.getNumPages(),
            )
            header_pdf = _get_header_pdf(page.cropBox.getHeight(), header_text)
            header_page = header_pdf.getPage(0)
            page.mergePage(header_page)
            pdf_writer.addPage(page)
    output = StringIO()
    pdf_writer.write(output)
    output.seek(0)
    response = HttpResponse(output, mimetype='application/pdf')
    response['Content-Disposition'] = 'inline; filename=with_header.pdf'
    return response
