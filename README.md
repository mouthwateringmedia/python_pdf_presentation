# Automating PDFs with Python and command-line tools
### by Edwin Grubbs <egrubbs@mwmdigital.com>
Presented at [PyHou Meetup](http://www.meetup.com/python-14/)

-------------------------------------------------------------


## Presentation

To view it as a slideshow, just run

```python ./console-presenter/present.py presentation.txt```

Otherwise, you can just read the presentation.txt file.

*BTW, console-presenter is actually hosted at [launchpad.net](https://code.launchpad.net/~registry/console-presenter/trunk), but it's small, and I didn't want to require people to install bzr just to play with it.*

## Requirements

You can get wkhtmltopdf 0.12.0 binaries from [http://wkhtmltopdf.org/downloads.html](http://wkhtmltopdf.org/downloads.html)

You can get PyPDF2 and reportlab plus the dependencies for the Django example just by running:

```pip install -r requirements.txt```

## Running Django Example

1. Edit the WKHTMLTOPDF_PATH setting in ```django_example/main/settings.py```
1. Run: ```python django_example/manage.py syncdb``
