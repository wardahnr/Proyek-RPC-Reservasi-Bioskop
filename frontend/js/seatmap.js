const ROWS = ["A", "B", "C", "D", "E"];
const COLUMNS = Array.from({ length: 10 }, (_, index) => index + 1);

export function renderSeatmap(container, seats, selectedSeat, onSelect, raceSelectedSeat) {
  const fragment = document.createDocumentFragment();
  const corner = document.createElement("span");
  corner.setAttribute("aria-hidden", "true");
  fragment.append(corner);

  for (const column of COLUMNS) {
    const label = document.createElement("span");
    label.className = "column-label";
    label.textContent = String(column);
    fragment.append(label);
  }

  for (const row of ROWS) {
    const rowLabel = document.createElement("span");
    rowLabel.className = "row-label";
    rowLabel.textContent = row;
    fragment.append(rowLabel);

    for (const column of COLUMNS) {
      const id = `${row}${column}`;
      const seat = seats.get(id) || { kursi_id: id, status: "TERSEDIA", pemesan: "" };
      const button = document.createElement("button");
      const booked = seat.status === "TERPESAN";
      const selected = selectedSeat === id;
      const raceSelected = raceSelectedSeat === id;
      button.type = "button";
      button.className = `seat ${booked ? "booked" : "available"}${selected ? " selected" : ""}${raceSelected ? " race-selected" : ""}`;
      button.dataset.seatId = id;
      button.textContent = String(column);
      button.setAttribute(
        "aria-label",
        booked
          ? `Kursi ${id}, terpesan oleh ${seat.pemesan || "pemesan"}`
          : `Kursi ${id}, ${selected ? "dipilih" : "tersedia"}`,
      );
      if (booked && seat.pemesan) button.title = `Terpesan oleh ${seat.pemesan}`;
      button.addEventListener("click", () => onSelect(seat));
      fragment.append(button);
    }
  }
  container.replaceChildren(fragment);
}

export function flashSeat(container, id) {
  const button = container.querySelector(`[data-seat-id="${CSS.escape(id)}"]`);
  if (!button) return;
  button.classList.remove("flash");
  requestAnimationFrame(() => button.classList.add("flash"));
  button.addEventListener("animationend", () => button.classList.remove("flash"), { once: true });
}
