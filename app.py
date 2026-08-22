import io
import os
import re
import time
import requests
from flask import Flask, request, send_file, jsonify, render_template
from fpdf import FPDF
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)

# Use bundled fonts if present (for cloud deploys), else system fonts
_LOCAL_FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_DIR = _LOCAL_FONTS if os.path.exists(os.path.join(_LOCAL_FONTS, "DejaVuSans.ttf")) \
    else "/usr/share/fonts/truetype/dejavu"

# ---------------------------------------------------------------- helpers

def extract_video_id(url: str):
    url = url.strip()
    patterns = [
        r"(?:v=|/videos?/|embed/|shorts/|youtu\.be/|/v/|/e/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_metadata(video_id: str):
    r = requests.get(
        "https://www.youtube.com/oembed",
        params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    return r.json()


def get_thumbnail(video_id: str):
    for name in ("maxresdefault", "hqdefault", "mqdefault"):
        try:
            r = requests.get(f"https://i.ytimg.com/vi/{video_id}/{name}.jpg", timeout=15)
            if r.status_code == 200 and len(r.content) > 2000:
                return r.content
        except Exception:
            pass
    return None


def _make_api():
    """YouTubeTranscriptApi with optional proxy (set env vars on your host):
       WEBSHARE_USER + WEBSHARE_PASS  -> Webshare rotating residential proxies
       PROXY_URL                      -> any generic http/https proxy url"""
    ws_user = os.environ.get("WEBSHARE_USER")
    ws_pass = os.environ.get("WEBSHARE_PASS")
    proxy_url = os.environ.get("PROXY_URL")
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
            proxy_username=ws_user, proxy_password=ws_pass))
    if proxy_url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(
            http_url=proxy_url, https_url=proxy_url))
    return YouTubeTranscriptApi()


def get_transcript(video_id: str):
    """Return (list of {start, text}, language) or (None, error_message)."""
    try:
        api = _make_api()
        try:
            fetched = api.fetch(video_id)
        except Exception:
            # fall back to any available transcript (incl. auto-generated / other langs)
            tl = api.list(video_id)
            transcript = None
            for t in tl:
                transcript = t
                if t.language_code.startswith("en"):
                    break
            if transcript is None:
                return None, "No transcript available"
            fetched = transcript.fetch()
        snippets = [{"start": s.start, "text": s.text.replace("\n", " ").strip()}
                    for s in fetched.snippets]
        return snippets, fetched.language
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def fmt_ts(seconds: float):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chunk_transcript(snippets, interval=60):
    """Group transcript snippets into paragraphs of ~interval seconds."""
    chunks = []
    cur_start, cur_text = None, []
    for sn in snippets:
        if cur_start is None:
            cur_start = sn["start"]
        cur_text.append(sn["text"])
        if sn["start"] - cur_start >= interval:
            chunks.append((cur_start, " ".join(t for t in cur_text if t)))
            cur_start, cur_text = None, []
    if cur_text:
        chunks.append((cur_start or 0, " ".join(t for t in cur_text if t)))
    return chunks


# ---------------------------------------------------------------- PDF

ACCENT = (204, 0, 0)          # YouTube red
DARK = (33, 33, 33)
GREY = (110, 110, 110)
LIGHT = (245, 245, 245)


class JournalPDF(FPDF):
    def __init__(self, title):
        super().__init__(format="A4")
        self.video_title = title
        self.add_font("DejaVu", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", "I", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(*GREY)
        title = self.video_title
        if len(title) > 70:
            title = title[:67] + "..."
        self.cell(0, 8, title, align="L")
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.4)
        self.line(10, 16, 200, 16)
        self.ln(12)

    def footer(self):
        self.set_y(-14)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 8, f"Page {self.page_no()}  ·  Generated by YouTube Journal", align="C")


def build_pdf(video_id, meta, thumb, snippets, lang, err):
    title = meta.get("title", "Untitled video")
    author = meta.get("author_name", "Unknown channel")
    url = f"https://www.youtube.com/watch?v={video_id}"

    pdf = JournalPDF(title)

    # ---------- cover page ----------
    pdf.add_page()
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, 210, 6, "F")

    pdf.set_y(22)
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 8, "VIDEO JOURNAL", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 10, title, align="C")

    pdf.ln(2)
    pdf.set_font("DejaVu", "", 12)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 8, f"by {author}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if thumb:
        img = io.BytesIO(thumb)
        img_w = 150
        x = (210 - img_w) / 2
        pdf.image(img, x=x, w=img_w)
        pdf.ln(8)

    # info box
    pdf.set_fill_color(*LIGHT)
    box_y = pdf.get_y()
    pdf.rect(25, box_y, 160, 34, "F")
    pdf.set_y(box_y + 5)

    def info_row(label, value, link=None):
        pdf.set_x(32)
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*DARK)
        pdf.cell(30, 7, label)
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*(ACCENT if link else GREY))
        pdf.cell(0, 7, value, link=link or "", new_x="LMARGIN", new_y="NEXT")

    info_row("Link", url, link=url)
    info_row("Channel", author)
    info_row("Journal date", time.strftime("%d %B %Y"))
    pdf.ln(8)

    # ---------- transcript pages ----------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "Transcript", new_x="LMARGIN", new_y="NEXT")

    if snippets:
        pdf.set_font("DejaVu", "I", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(0, 6, f"Language: {lang}  ·  {len(snippets)} caption segments",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        for start, text in chunk_transcript(snippets, interval=60):
            if not text:
                continue
            pdf.set_font("DejaVu", "B", 9)
            pdf.set_text_color(*ACCENT)
            pdf.cell(0, 6, f"[{fmt_ts(start)}]",
                     link=f"{url}&t={int(start)}s", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 5.6, text)
            pdf.ln(2.5)
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6,
            "No transcript could be retrieved for this video "
            "(captions may be disabled).\n\nDetails: " + str(err))

    # ---------- notes page ----------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "My Notes", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    y = pdf.get_y()
    while y < 265:
        pdf.line(12, y, 198, y)
        y += 10

    return bytes(pdf.output())


# ---------------------------------------------------------------- routes

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "That doesn't look like a valid YouTube link."}), 400

    meta = get_metadata(video_id)
    if meta is None:
        return jsonify({"error": "Video not found or unavailable."}), 404

    thumb = get_thumbnail(video_id)
    snippets, lang_or_err = get_transcript(video_id)
    lang = lang_or_err if snippets else None
    err = None if snippets else lang_or_err

    try:
        pdf_bytes = build_pdf(video_id, meta, thumb, snippets, lang, err)
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}"}), 500

    safe_title = re.sub(r"[^\w\s-]", "", meta.get("title", video_id)).strip()[:60] or video_id
    filename = f"{safe_title} - journal.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
