# Co-author Network 렌더링 성능 개선 가이드

현재 구현: Canvas 2D + d3-force, 26k 노드 / 82k 엣지 / threshold 슬라이더.  
아래 5가지를 우선순위 순으로 적용하면 됨. 1~3번만 해도 체감 차이 큼.

---

## 1. Edge stroke 배칭 ← 지금 코드의 최대 병목

**현황**: `_make_coauthor_network.py`가 생성하는 HTML의 `draw()` 함수에서
엣지마다 `ctx.stroke()`를 개별 호출하고 있음.
82k 엣지 × 60fps = **490만 draw call/초** — Canvas 2D의 단일 최대 병목.

```js
// 현재 (느림)
for (const e of edges) {
  ctx.beginPath();
  ctx.lineWidth = eScale(e.weight) * wMult;
  ctx.moveTo(e.source.x, e.source.y);
  ctx.lineTo(e.target.x, e.target.y);
  ctx.stroke();  // ← 엣지마다 GPU flush
}

// 개선: weight를 2~3 버킷으로 quantize, 버킷별 path 하나에 몰아서 stroke() 1번
const buckets = { thin: [], mid: [], thick: [] };
for (const e of edges) {
  const w = eScale(e.weight);
  (w < 1.2 ? buckets.thin : w < 2.5 ? buckets.mid : buckets.thick).push(e);
}
for (const [lw, group] of [[0.8, buckets.thin], [1.8, buckets.mid], [3.5, buckets.thick]]) {
  ctx.beginPath();
  ctx.lineWidth = lw * wMult;
  for (const e of group) {
    ctx.moveTo(e.source.x, e.source.y);
    ctx.lineTo(e.target.x, e.target.y);
  }
  ctx.stroke();  // ← 버킷당 1번
}
```

**효과**: 렌더 1프레임 시간 5~10배 단축. 특히 슬라이더 threshold 낮췄을 때(엣지 많을 때) 극적.

**구현 위치**: `pipeline/_make_coauthor_network.py`의 `draw()` 함수 생성 부분.

---

## 2. Layout 사전 계산 후 JSON에 좌표 저장

**현황**: 페이지 열 때마다 d3-force simulation이 처음부터 수렴까지 돌아감.
26k 노드 기준 수렴까지 수초 + 그동안 UI janking.

**개선**: `_make_coauthor_network.py`에서 네트워크 생성 시점에
Python으로 layout을 미리 계산해서 `x`, `y`를 JSON에 저장.
브라우저는 simulation 없이 바로 그릴 수 있음.

```python
# pipeline/_make_coauthor_network.py 에 추가 (networkx 사용)
import networkx as nx

G = nx.Graph()
for n in nodes: G.add_node(n['id'])
for e in edges: G.add_edge(e['source'], e['target'], weight=e['weight'])

pos = nx.spring_layout(G, seed=42, k=2/len(nodes)**0.5, iterations=100)
id_to_node = {n['id']: n for n in nodes}
for nid, (x, y) in pos.items():
    id_to_node[nid]['x'] = float(x) * 4000  # canvas 좌표계로 스케일
    id_to_node[nid]['y'] = float(y) * 4000
```

브라우저 JS에서는 저장된 좌표로 노드 초기화:

```js
// simulation 선언 시 alphaDecay를 높여 빠르게 수렴하거나, 아예 stop()
const simulation = d3.forceSimulation(nodes)
  .alphaDecay(0.1)   // 기본 0.0228보다 빠르게 식힘
  // ...
  .on('end', () => simulation.stop());

// 또는 좌표가 있으면 simulation 건너뜀
if (nodes[0].x != null) simulation.stop();
```

**효과**: 페이지 로드 즉시 그래프 표시. 초기 janking 완전 제거.  
**주의**: layout 재계산은 Python 단에서 ~30초 걸릴 수 있음. `_make_coauthor_network.py` 실행 시간 늘어남.

---

## 3. Simulation과 렌더링 분리 (RAF loop)

**현황**: `simulation.on('tick', draw)` — simulation이 한 tick 계산할 때마다 draw() 호출.
simulation의 내부 tick rate는 고정되어 있지 않고 가능한 한 빨리 돎 → 불필요한 렌더 발생.

**개선**: dirty flag + `requestAnimationFrame` 루프로 렌더를 60fps로 캡.

```js
let positionsDirty = false;
simulation.on('tick', () => { positionsDirty = true; });

function loop() {
  if (positionsDirty) {
    draw();
    positionsDirty = false;
  }
  requestAnimationFrame(loop);
}
loop();
```

**효과**: 고주사율 모니터에서도 60fps 이상 렌더 방지. 저사양 기기에서 simulation 진행 중 프레임 드롭 감소.

---

## 4. Viewport culling

**현황**: 사용자가 pan/zoom으로 일부만 보고 있어도 화면 밖 26k 노드를 전부 그림.

**개선**: 현재 transform 기준 viewport bbox 밖 노드·엣지는 skip.

```js
function draw() {
  // ...
  const margin = 50;
  const x0 = (0 - transform.x) / transform.k - margin;
  const y0 = (0 - transform.y) / transform.k - margin;
  const x1 = (width  - transform.x) / transform.k + margin;
  const y1 = (height - transform.y) / transform.k + margin;

  for (const n of nodes) {
    if (n.x < x0 || n.x > x1 || n.y < y0 || n.y > y1) continue;
    // draw node
  }
  for (const e of edges) {
    const sx = e.source.x, sy = e.source.y, tx = e.target.x, ty = e.target.y;
    if (Math.max(sx, tx) < x0 || Math.min(sx, tx) > x1) continue;
    if (Math.max(sy, ty) < y0 || Math.min(sy, ty) > y1) continue;
    // draw edge
  }
}
```

**효과**: 줌인 상태에서 렌더 비용이 화면에 보이는 노드 수에 비례하여 감소.  
엣지 culling은 간단한 AABB check라 overhead 무시할 수준.

---

## 5. 규모 확장 시 — WebGL (Sigma.js)

**현황**: Canvas 2D는 노드 ~3만, 엣지 ~10만이 실용 한계.  
현재(26k / 82k)는 한계 근처.

**트리거**: 수집 venue가 20개 초과하거나 노드 50k / 엣지 150k 돌파 시점에 전환 고려.

**권장 라이브러리**: [Sigma.js v2](https://www.sigmajs.org/) — graphology 기반, WebGL 렌더러, d3 안 쓰고도 동일한 인터랙션 구현 가능.

```bash
npm install sigma graphology graphology-layout-forceatlas2
```

WebGL은 GPU 없는 환경에서도 소프트웨어 폴백(SwiftShader)으로 동작.
2025년 기준 브라우저 지원율 98%+ — 호환성 이슈 없음.

**효과**: 노드 100만 / 엣지 1000만도 60fps 렌더 가능.  
**비용**: HTML 생성 로직 전면 재작성 필요. 1~4번과 달리 큰 리팩터링.

---

## 우선순위 요약

| 순위 | 작업 | 난이도 | 효과 |
|:---:|---|:---:|---|
| 1 | Edge stroke 배칭 | 낮음 | 렌더 5~10배 빠름 |
| 2 | Layout 사전 계산 (pre-bake) | 중간 | 로딩 janking 제거 |
| 3 | RAF 분리 | 낮음 | 60fps 안정화 |
| 4 | Viewport culling | 낮음 | 줌인 시 비용 절감 |
| 5 | WebGL (Sigma.js) | 높음 | 10배 규모 확장 |

1~3번만 적용해도 현재 규모에서 체감 차이 큼.  
당장 구현 요청하면 `_make_coauthor_network.py` 수정으로 반영 가능.
