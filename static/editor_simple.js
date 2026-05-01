let elements = [];
let selected = [];

function addText() {
  elements.push({
    type: "text",
    text: "Sample Text",
    position: [20, 20],
    width: 200,
    height: 40
  });
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
      selected = [index];
      loadProperties();
      renderCanvas();
    };

    div.ondblclick = () => {
      if (el.type === "text") {
        const newText = prompt("Edit text", el.text || "");
        if (newText !== null) {
          el.text = newText;
          renderCanvas();
        }
      }
    };

    div.onmousedown = e => startDrag(e, index);

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
  };
}

function loadProperties() {
  const textEl = document.getElementById("prop-text");

  if (selected.length === 1) {
    const el = elements[selected[0]];
    textEl.value = el.type === "text" ? el.text : "";
  } else {
    textEl.value = "";
  }
}

function updateSelectedText() {
  const v = document.getElementById("prop-text").value;
  selected.forEach(i => {
    if (elements[i].type === "text") elements[i].text = v;
  });
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

function deleteTemplate() {
  const name = document.getElementById("template-name").value;
  if (!name) return alert("Enter a name");

  fetch("/api/delete_template", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name})
  }).then(() => alert("Deleted"));
}

renderCanvas();
