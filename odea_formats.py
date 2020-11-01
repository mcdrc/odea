FORMATS = {
    'raster image': {
        'ext': ['bmp', 'gif', 'jpg', 'jpeg', 'png', 'psd', 'tif', 'tiff'],
        'targets': [
            ('df-med-img', 'png'),
            ('df-lg-img', 'png'),
        ]
    },

    'web archive': {
        'ext': ['url'],
        'targets': [
            ('pf-webarc', 'webarc'),
        ]
    },

    'plain text or Markdown': {
        'ext': ['md', 'txt'],
        'targets': [
            ('df-pandoc-html', 'html')
        ]
    },

    'reStructuredText': {
        'ext': ['rst'],
        'targets': [
            ('df-docutils-html', 'html')
        ]
    },

    'audio file': {
        'ext': ['mp3', 'wav', 'wma', 'ogg'],
        'targets': [
            ('pf-wav', 'wav'),
            ('df-mp3', 'mp3'),
        ]
    },

    'office document': {
        'ext': ['odt', 'odp', 'doc', 'docx', 'ppt', 'pptx'],
        'targets': [
            ('df-pdf-doc', 'pdf'),
        ]
    },

    'vector image': {
        'ext': ['eps', 'svg'],
        'targets': [
            ('pf-vector', 'svg'),
            ('df-pdf-vector', 'pdf')
        ]
    },

    'video': {
        'ext': ['avi', 'flv', 'mov', 'mpeg', 'mp4', 'webm', 'ogv'],
        'targets': [
            ('df-360p-vp9-400k', 'webm'),
            ('df-video-still', 'jpg'), # frame
            ('df-h264', 'mp4'),
    }


# VIDEO:
frame = int(float(odea._get_duration(f.filename), // 2)
