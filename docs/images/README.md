# Screenshots & Demo Assets

Current assets referenced by `README.md` / `README_EN.md`:

| File | Content |
|------|---------|
| `screenshot-main.jpg` | Main editor view — no document open, requirement typed directly into the instruction bar |
| `screenshot-settings.jpeg` | Settings page — style learning & style templates |
| `demo.mp4` | 37s demo: requirement → auto-created document → Agent web search + full draft |

Still welcome (add the file, then add a row to the README preview tables):

| File | Content suggestion |
|------|--------------------|
| `screenshot-diff.png` | AI edit with real-time diff preview (accept / reject) |
| `screenshot-agent.png` | Agent mode tool-call timeline |
| `screenshot-branches.png` | Multi-branch / multi-target view |

Tips:

- JPG/PNG for screenshots; MP4 (H.264, ≤1 MB/min preferred) for recordings.
- Compress videos before committing (`ffmpeg -i in.mp4 -vf scale=-2:720 -c:v libx264 -crf 30 -an out.mp4`) to keep the repo small.
- For an inline-playable video in the README, drag the mp4 into the GitHub web README editor and use the generated `user-attachments` URL.
