let currentPair = { aModel: null, bModel: null };

async function fetchRankings() {
  const res = await fetch('/api/rankings');
  const data = await res.json();
  const tbody = document.getElementById('leaderboardBody');
  tbody.innerHTML = '';
  for (const row of data) {
    const tr = document.createElement('tr');
    const tdModel = document.createElement('td');
    tdModel.textContent = row.id;
    const tdRating = document.createElement('td');
    tdRating.textContent = Math.round(row.rating);
    tr.appendChild(tdModel);
    tr.appendChild(tdRating);
    tbody.appendChild(tr);
  }
}

async function compare() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) return;
  const model_a = document.getElementById('modelA').value || undefined;
  const model_b = document.getElementById('modelB').value || undefined;
  document.getElementById('compareSection').classList.remove('hidden');
  const responseA = document.getElementById('responseA');
  const responseB = document.getElementById('responseB');
  responseA.textContent = '';
  responseB.textContent = '';

  const res = await fetch('/api/compare/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, model_a, model_b })
  });
  if (!res.ok || !res.body) {
    alert('Streaming error');
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 1);
      if (!line.trim()) continue;
      try {
        const evt = JSON.parse(line);
        if (evt.type === 'meta') {
          currentPair.aModel = evt.a_model;
          currentPair.bModel = evt.b_model;
        } else if (evt.type === 'delta') {
          if (evt.side === 'a') responseA.textContent += evt.text;
          if (evt.side === 'b') responseB.textContent += evt.text;
        }
      } catch {}
    }
  }
}

async function sendOutcome(outcome) {
  if (!currentPair.aModel || !currentPair.bModel) return;
  let winner_id = null;
  let loser_id = null;
  if (outcome === 'left') {
    winner_id = currentPair.aModel; loser_id = currentPair.bModel;
  } else if (outcome === 'right') {
    winner_id = currentPair.bModel; loser_id = currentPair.aModel;
  } else if (outcome === 'tie' || outcome === 'both_bad') {
    winner_id = currentPair.aModel; loser_id = currentPair.bModel;
  }
  const res = await fetch('/api/vote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcome, winner_id, loser_id })
  });
  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }
  await fetchRankings();
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('compareBtn').addEventListener('click', compare);
  document.getElementById('voteA').addEventListener('click', () => sendOutcome('left'));
  document.getElementById('voteB').addEventListener('click', () => sendOutcome('right'));
  document.getElementById('voteTie').addEventListener('click', () => sendOutcome('tie'));
  document.getElementById('voteBothBad').addEventListener('click', () => sendOutcome('both_bad'));
  fetchRankings();
  // Populate model selectors
  fetch('/api/models').then(r => r.json()).then(models => {
    const a = document.getElementById('modelA');
    const b = document.getElementById('modelB');
    for (const m of models) {
      const optA = document.createElement('option');
      optA.value = m.id; optA.textContent = `${m.display_name} (${m.id})`;
      a.appendChild(optA);
      const optB = document.createElement('option');
      optB.value = m.id; optB.textContent = `${m.display_name} (${m.id})`;
      b.appendChild(optB);
    }
  });
});


