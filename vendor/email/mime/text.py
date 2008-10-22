# Copyright (C) 2001-2006 Python Software Foundation
# Author: Barry Warsaw
# Contact: email-sig@python.org
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

"""Class representing text/* type MIME documents."""

__all__ = ['MIMEText']

from email.encoders import encode_7or8bit
from email.mime.nonmultipart import MIMENonMultipart



class MIMEText(MIMENonMultipart):
    """Class for generating text/* type MIME documents."""

    def __init__(self, _text, _subtype='plain', _charset='us-ascii'):
        """Create a text/* type MIME document.

        _text is the string for this message object.

        _subtype is the MIME sub content type, defaulting to "plain".

        _charset is the character set parameter added to the Content-Type
        header.  This defaults to "us-ascii".  Note that as a side-effect, the
        Content-Transfer-Encoding header will also be set.
        """
        MIMENonMultipart.__init__(self, 'text', _subtype,
                                  **{'charset': _charset})
        self.set_payload(_text, _charset)
