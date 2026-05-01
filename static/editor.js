let elements = [];
let selected = [];
let history = [];
let historyIndex = -1;

function pushHistory() {
  history = history.slice(0, historyIndex + 1);
  history.push(JSON.stringify(elements));
  historyIndex++;
}

function undo() {
  if (historyIndex <= 0) return;
  historyIndex--;
  elements = JSON.parse(history[historyIndex]);
  renderCanvas();
}

function redo() {
  if (historyIndex >= history.length - 1) return;
  historyIndex++;
  elements = JSON.parse(history[historyIndex]);
  renderCanvas();
}

function addText() {
  elements.push({
    type: "text",
    text: "Sample Text",
    font: "DejaVuSans.ttf",
    size: 32,
    position: [20, 20],
    width: 200,
    height: 40
  });
  pushHistory();
  renderCanvas();
}

function addQR() {
  elements.push({
    type: "qr",
    field: "qr",
    position: [20, 20],
    width: 100,
    height: 100
  });
  pushHistory();
  renderCanvas();
}

function triggerImageUpload() {
  document.getElementById("image-upload").click();
}

function uploadImage() {
  const file = document.getElementById("image-upload").files[0];
  if (!file) return;

  const form = new FormData();
  form.append("image", file);

  fetch("/api/upload_template_image", {
    method: "POST",
    body: form
  })
  .then(r => r.json())
  .then(data => {
    elements.push({
      type: "image",
      source: data.filename,
      position: [20, 20],
      width: 150,
      height: 100
    });
    pushHistory();
    renderCanvas();
  });
}

function renderCanvas() {
  const canvas = document.getElementById("canvas");
  canvas.innerHTML = "";

  elements.forEach((el, index) => {
    const div = document.createElement("div");
    div.className = "element";
    div.style.left = el.position[0] + "px";
    div.style.top = el.position[1] + "px";
    div.style.width = el.width + "px";
    div.style.height = el.height + "px";
    div.dataset.index = index;

    if (selected.includes(index)) div.classList.add("selected");

    div.innerText = el.type === "text" ? el.text : el.type.toUpperCase();

    div.onclick = e => {
      e.stopPropagation();
      if (e.shiftKey) {
        if (!selected.includes(index)) selected.push(index);
      } else {
        selected = [index];
      }
      loadProperties();
      renderCanvas();
    };

    div.ondblclick = () => {
      if (el.type === "text") {
        const newText = prompt("Edit text", el.text || "");
        if (newText !== null) {
          el.text = newText;
          pushHistory();
          renderCanvas();
        }
      }
    };

    div.onmousedown = e => startDrag(e, index);

    const handle = document.createElement("div");
    handle.className = "resize-handle";
    handle.onmousedown = e => startResize(e, index);
    div.appendChild(handle);

    canvas.appendChild(div);
  });

  canvas.onclick = () => {
    selected = [];
    loadProperties();
    renderCanvas();
  };
}

function startDrag(e, index) {
  const el = elements[index];
  const startX = e.clientX;
  const startY = e.clientY;
  const origX = el.position[0];
  const origY = el.position[1];

  function move(ev) {
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;

    el.position[0] = Math.round((origX + dx) / 10) * 10;
    el.position[1] = Math.round((origY + dy) / 10) * 10;

    renderCanvas();
  }

  document.onmousemove = move;
  document.onmouseup = () => {
    document.onmousemove = null;
    pushHistory();
  };
}

function startResize(e, index) {
  e.stopPropagation();

  const el = elements[index];
  const startX = e.clientX;
  const startY = e.clientY;
  const origW = el.width;
  const origH = el.height;

  function move(ev) {
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;

    el.width = Math.max(20, Math.round((origW + dx) / 10) * 10);
    el.height = Math.max(20, Math.round((origH + dy) / 10) * 10);

    renderCanvas();
  }

  document.onmousemove = move;
  document.onmouseup = () => {
    document.onmousemove = null;
    pushHistory();
  };
}

function loadProperties() {
  const fontEl = document.getElementById("prop-font");
  const sizeEl = document.getElementById("prop-size");
  const textEl = document.getElementById("prop-text");

  if (selected.length === 1) {
    const el = elements[selected[0]];

    if (el.type === "text") {
      fontEl.value = el.font || "DejaVuSans.ttf";
      sizeEl.value = el.size || 32;
      textEl.value = el.text || "";
    } else {
      fontEl.value = "DejaVuSans.ttf";
      sizeEl.value = "";
      textEl.value = "";
    }
  } else {
    fontEl.value = "DejaVuSans.ttf";
    sizeEl.value = "";
    textEl.value = "";
  }
}

function updateSelectedFont() {
  const v = document.getElementById("prop-font").value;
  selected.forEach(i => {
    if (elements[i].type === "text") elements[i].font = v;
  });
  pushHistory();
  renderCanvas();
}

function updateSelectedSize() {
  const v = parseInt(document.getElementById("prop-size").value);
  selected.forEach(i => {
    if (elements[i].type === "text") elements[i].size = v;
  });
  pushHistory();
  renderCanvas();
}

function updateSelectedText() {
  const v = document.getElementById("prop-text").value;
  selected.forEach(i => {
    if (elements[i].type === "text") elements[i].text = v;
  });
  pushHistory();
  renderCanvas();
}

function bringToFront() {
  selected.forEach(i => {
    const el = elements.splice(i, 1)[0];
    elements.push(el);
  });
  pushHistory();
  renderCanvas();
}

function sendToBack() {
  selected.forEach(i => {
    const el = elements.splice(i, 1)[0];
    elements.unshift(el);
  });
  pushHistory();
  renderCanvas();
}

function saveTemplate() {
  const name = document.getElementById("template-name").value;
  if (!name) return alert("Enter a name");

  fetch("/api/save_template", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name, elements})
  }).then(() => alert("Saved"));
}

function duplicateTemplate() {
  const name = document.getElementById("template-name").value;
  if (!name) return alert("Enter a name first");

  const newName = name + "_copy";

  fetch("/api/save_template", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name: newName, elements})
  }).then(() => alert("Duplicated as " + newName));
}

function deleteTemplate() {
  const name = document.getElementById("template-name").value;
  if (!name) return alert("Enter a name");

  fetch("/api/delete_template", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name})
  }).then(() => alert("Deleted"));
}

function exportTemplate() {
  const name = document.getElementById("template-name").value;
  if (!name) return alert("Enter a name");

  fetch("/api/export_template?name=" + encodeURIComponent(name))
    .then(r => r.json())
    .then(data => {
      const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name + ".json";
      a.click();
      URL.revokeObjectURL(url);
    });
}

function importTemplate() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "application/json";

  input.onchange = () => {
    const file = input.files[0];
    const reader = new FileReader();

    reader.onload = () => {
      const data = JSON.parse(reader.result);
      elements = data.elements || [];
      document.getElementById("template-name").value = data.name || "";
      pushHistory();
      renderCanvas();
    };

    reader.readAsText(file);
  };

  input.click();
}

pushHistory();
renderCanvas();
