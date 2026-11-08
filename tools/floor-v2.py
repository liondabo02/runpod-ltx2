import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\office_floor.py")
t = p.read_text(encoding="utf-8")

t = t.replace(
    "const ROOM_W = 300, ROOM_H = 210, GAP = 26, MARGIN = 40, TOP = 70;",
    "const ROOM_W = 300, ROOM_H = 210, GAP = 26, MARGIN = 40, TOP = 190;",
)

t = t.replace(
    """  rooms = departments.map((dep, i) => {
    const col = i % perRow, row = Math.floor(i / perRow);
    const x = MARGIN + col * (ROOM_W + GAP);""",
    """  rooms = departments.map((dep, i) => {
    const col = i % perRow, row = Math.floor(i / perRow);
    const count = Math.min(8, Math.max(1, (dep.workers || []).length));
    const w = 220 + count * 22;
    const x = MARGIN + col * (ROOM_W + GAP);""",
)

t = t.replace(
    """      x, y, state: dep.state, busy: dep.state === 'çalışıyor',
      desks, coffee: { x: x + ROOM_W - 46, y: y + ROOM_H - 34 },
      workers""",
    """      x, y, w, state: dep.state, busy: dep.state === 'çalışıyor',
      desks, coffee: { x: x + w - 46, y: y + ROOM_H - 34 },
      door: { x: x + 18, y: y + ROOM_H - 12 },
      workers""",
)

t = t.replace(
    "function drawFloor(){",
    """const ZONES = [
  { label: '🛎️ Resepsiyon', x: 40, y: 84, w: 300, h: 84, color: '#132038' },
  { label: '🛋️ Ortak Alan · ☕ · 🏓', x: 356, y: 84, w: 470, h: 84, color: '#12233a' },
  { label: '👔 CEO Ofisi', x: 842, y: 84, w: 300, h: 84, color: '#1b2033' }
];

function drawZones(){
  ZONES.forEach(z => {
    ctx.fillStyle = z.color;
    roundRect(z.x, z.y, z.w, z.h, 14); ctx.fill();
    ctx.strokeStyle = '#243450'; ctx.lineWidth = 1;
    roundRect(z.x, z.y, z.w, z.h, 14); ctx.stroke();
    ctx.fillStyle = '#9db0d0'; ctx.font = 'bold 12px system-ui';
    ctx.fillText(z.label, z.x + 12, z.y + 22);
  });
}

function drawFloor(){""",
)

t = t.replace(
    """  drawFloor();
  drawRooms();""",
    """  drawFloor();
  drawZones();
  drawRooms();""",
)

t = t.replace("roundRect(room.x, room.y, ROOM_W, ROOM_H, 16); ctx.fill();",
              "roundRect(room.x, room.y, room.w, ROOM_H, 16); ctx.fill();")
t = t.replace("roundRect(room.x, room.y, ROOM_W, ROOM_H, 16); ctx.stroke();",
              "roundRect(room.x, room.y, room.w, ROOM_H, 16); ctx.stroke();")
t = t.replace("ctx.fillText(room.state, room.x + ROOM_W - 74, room.y + 22);",
              "ctx.fillText(room.state, room.x + room.w - 74, room.y + 22);")

t = t.replace(
    "    a.seed += dt * (a.state === 'çalışıyor' ? 7 : 2.2);",
    """    a.seed += dt * (a.state === 'çalışıyor' ? 7 : 2.2);
    // Kapıdan giriş: masaya gitmeden önce oda kapısına yürü.
    if (a.room && a.doorX === undefined){ a.doorX = a.room.door.x; a.doorY = a.room.door.y; }""",
)

p.write_text(t, encoding="utf-8")
print("v2 uygulandı:", "drawZones" in t, "| zona:", "CEO Ofisi" in t, "| oda w:", "room.w" in t)
