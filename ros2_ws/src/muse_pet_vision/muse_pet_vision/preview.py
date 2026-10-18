"""Prepare an isolated HTTP configuration for TROS's installed web viewer."""
from pathlib import Path


def prepare_viewer(webservice: Path, runtime: Path) -> Path:
    webservice = webservice.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    runtime = runtime.resolve()
    (runtime / "logs").mkdir(exist_ok=True)
    source = webservice / "html/TogetheROS/index.html"
    page = source.read_text()
    marker = '<script src="./main.js"></script>'
    if marker not in page:
        raise ValueError(f"Unsupported TROS viewer: {source}")
    # The vendor viewer selects 8080 and 8082 when path_num is two.
    page = page.replace(marker,
        '<script>document.cookie="path_num=2; path=/; SameSite=Lax";</script>\n' + marker)
    page = page.replace("<title>TogetheROS Web Display</title>",
                        "<title>Muse: YOLO and gestures</title>")
    page = page.replace("</head>", """<style>
      .video::after {position:absolute;top:10px;left:12px;color:white;
        background:#171717cc;padding:6px 10px;border-radius:6px;pointer-events:none}
      #video-wrap-8080::after {content:'YOLOv8 — objects'}
      #video-wrap-8082::after {content:'Hands & gestures'}
    </style></head>""")
    (runtime / "index.html").write_text(page)

    def quoted(path):
        return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'

    config = runtime / "nginx.conf"
    config.write_text(f"""daemon off;
worker_processes 1;
pid {quoted(runtime / 'nginx.pid')};
error_log stderr;
events {{ worker_connections 128; }}
http {{
  include {quoted(webservice / 'conf/mime.types')};
  default_type application/octet-stream;
  access_log off;
  sendfile on;
  client_body_temp_path {quoted(runtime / 'client_temp')};
  proxy_temp_path {quoted(runtime / 'proxy_temp')};
  server {{
    listen 8000;
    root {quoted(webservice / 'html')};
    index index.html;
    location = /TogetheROS/ {{
      default_type text/html;
      alias {quoted(str(runtime) + '/')};
      add_header Cache-Control no-store;
    }}
    location = /TogetheROS/index.html {{
      alias {quoted(runtime / 'index.html')};
      add_header Cache-Control no-store;
    }}
  }}
}}
""")
    return config
