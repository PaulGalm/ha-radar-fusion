class RadarFusionHeatmapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._heatmapScale = "hourly";
    this._resizeObserver = null;
    this._updateInterval = null;
    this._updateFrequency = 1000; // Slower fetch
    this._lastHeatmapHash = null;
    this._pendingData = null;
    this._animationFrameId = null;
    this._isInitialized = false;
    this._renderInProgress = false;
  }

  connectedCallback() {
    if (!this._isInitialized) {
      this._isInitialized = true;
      this.startPolling();
    }
  }

  disconnectedCallback() {
    this.stopPolling();
  }

  startPolling() {
    if (this._updateInterval) return;
    this._updateInterval = setInterval(async () => {
      if (this._hass && this._config.config_entry_id) {
        const newData = await this.getFloorData();
        if (!newData || !newData.heatmap) return;

        // Hash only the heatmap data
        const heatmapHash = JSON.stringify(newData.heatmap[this._heatmapScale]);

        if (heatmapHash !== this._lastHeatmapHash) {
          this._lastHeatmapHash = heatmapHash;
          this._pendingData = newData;
          // Use requestAnimationFrame for smooth rendering
          if (this._animationFrameId)
            cancelAnimationFrame(this._animationFrameId);
          this._animationFrameId = requestAnimationFrame(() =>
            this.drawHeatmap(),
          );
        }
      }
    }, this._updateFrequency);
  }

  stopPolling() {
    if (this._updateInterval) {
      clearInterval(this._updateInterval);
      this._updateInterval = null;
    }
  }

  setConfig(config) {
    this._config = {
      config_entry_id: config.config_entry_id || null,
      width: config.width || 800,
      height: config.height || 600,
      grid_size: config.grid_size || 5000, // mm
      show_grid: config.show_grid === true,
      floor_id: config.floor_id || null,
      title: config.title || "Radar Fusion",
      floorplan_url: config.floorplan_url || null,
      floorplan_width_mm: config.floorplan_width_mm || null, // Physical width of floorplan in mm
      floorplan_height_mm: config.floorplan_height_mm || null, // Physical height of floorplan in mm
      offset_x: config.offset_x || 0, // Shift in mm
      offset_y: config.offset_y || 0, // Shift in mm
      // Migrate old decimal opacity (0.0-1.0) to new percentage (0-100)
      opacity: config.opacity !== undefined ? (config.opacity <= 1 ? config.opacity * 100 : config.opacity) : 50, // Heatmap opacity (0-100%)
      show_header: config.show_header !== false, // Show header with controls (default: true)
      show_legend: config.show_legend !== false, // Show stats (default: true)
    };
    // Load floorplan image if provided
    if (this._config.floorplan_url) {
      const img = new Image();
      img.onload = () => {
        this._floorplanImage = img;
        // Re-render when image loads to apply correct dimensions
        this.render();
      };
      img.onerror = () => {
        console.warn("Failed to load floorplan image");
      };
      img.src = this._config.floorplan_url;
    }
  }

  set hass(hass) {
    this._hass = hass;

    // Only initialize card on first hass assignment
    if (!this._isInitialized) {
      this._isInitialized = true;
      this.initializeCard();
    }
  }

  async initializeCard() {
    if (!this._hass) return;
    if (!this._config.config_entry_id) {
      const discovered = await this.discoverConfigEntry();
      if (!discovered) {
        this.renderError(
          "No Radar Fusion integration found. Please add it in Settings → Devices & Services.",
        );
        return;
      }
    }
    // Render UI only once
    this.render();
    // Start polling after render
    this.startPolling();
  }

  async updateCard() {
    // Only update canvas, not the entire card
    if (this._pendingData) {
      this.drawHeatmap();
    }
  }

  async discoverConfigEntry() {
    // Auto-discover radar_fusion config entry
    if (this._config.config_entry_id) return this._config.config_entry_id;

    try {
      console.log("Radar Fusion: Attempting auto-discovery...");

      // Look for any radar_fusion entity
      const states = this._hass.states;
      for (const entityId in states) {
        // Check if entity might belong to radar_fusion
        if (
          entityId.startsWith("binary_sensor.") ||
          entityId.startsWith("switch.")
        ) {
          try {
            const entityInfo = await this._hass.connection.sendMessagePromise({
              type: "config/entity_registry/get",
              entity_id: entityId,
            });

            if (
              entityInfo &&
              entityInfo.platform === "radar_fusion" &&
              entityInfo.config_entry_id
            ) {
              this._config.config_entry_id = entityInfo.config_entry_id;
              console.log(
                "Radar Fusion: Auto-discovered →",
                entityInfo.config_entry_id,
              );
              return entityInfo.config_entry_id;
            }
          } catch (err) {
            // Entity not in registry, skip
            continue;
          }
        }
      }

      console.warn(
        "Radar Fusion: No entities found. Please add sensors or zones first.",
      );
    } catch (error) {
      console.error("Radar Fusion: Discovery failed:", error);
    }

    return null;
  }

  render() {
    if (this._renderInProgress) return; // Prevent concurrent renders
    this._renderInProgress = true;

    // Calculate canvas dimensions based on floorplan if provided
    let canvasWidth = this._config.width;
    let canvasHeight = this._config.height;

    if (
      this._floorplanImage &&
      this._config.floorplan_width_mm &&
      this._config.floorplan_height_mm
    ) {
      // Use explicit dimensions
      const aspect =
        this._config.floorplan_width_mm / this._config.floorplan_height_mm;
      canvasHeight = Math.round(canvasWidth / aspect);
    } else if (this._floorplanImage && this._config.floorplan_width_mm) {
      // Calculate from image aspect ratio
      const imgAspect =
        this._floorplanImage.width / this._floorplanImage.height;
      canvasHeight = Math.round(canvasWidth / imgAspect);
    }

    const style = `
      <style>
        :host { display: block; padding: 16px; box-sizing: border-box; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .card-title { font-size: 20px; font-weight: 500; }
        .controls { display: flex; gap: 12px; }
        .toggle-btn { padding: 6px 12px; border: 1px solid var(--divider-color); border-radius: 4px; background: var(--card-background-color); cursor: pointer; font-size: 12px; transition: all 0.2s; }
        .toggle-btn.active { background: var(--primary-color); color: var(--text-primary-color); border-color: var(--primary-color); }
        .canvas-container { border: 1px solid var(--divider-color); border-radius: 4px; overflow: hidden; background: #1a1a1a; position: relative; width: 100%; aspect-ratio: ${canvasWidth} / ${canvasHeight}; }
        canvas { display: block; width: 100% !important; height: 100% !important; }
        .stats { margin-top: 12px; font-size: 12px; color: var(--secondary-text-color); }
      </style>
    `;
    const html = `
      ${style}
      ${this._config.show_header ? `
      <div class="card-header">
        <div class="card-title">${this._config.title}</div>
        <div class="controls">
          <select id="heatmap-scale" class="toggle-btn">
            <option value="hourly">Heatmap: hourly</option>
            <option value="24h">Heatmap: 24h</option>
            <option value="all_time">Heatmap: all-time</option>
          </select>
          <button class="toggle-btn" id="reset-heatmap">Reset heatmap</button>
        </div>
      </div>
      ` : ''}
      <div class="canvas-container">
        <canvas id="heatmapCanvas" width="${canvasWidth}" height="${canvasHeight}"></canvas>
      </div>
      ${this._config.show_legend ? `
      <div class="stats" id="stats"></div>
      ` : ''}
    `;
    this.shadowRoot.innerHTML = html;

    // Use event delegation on controls container
    const controls = this.shadowRoot.querySelector(".controls");
    controls.addEventListener("change", (ev) => {
      if (ev.target.id === "heatmap-scale") {
        this._heatmapScale = ev.target.value;
        this._lastHeatmapHash = null; // Reset hash to force redraw
        this.drawHeatmap(); // Only redraw canvas, not full render
      }
    });
    controls.addEventListener("click", async (ev) => {
      if (ev.target.id === "reset-heatmap") {
        await this.resetHeatmap();
        this._lastHeatmapHash = null; // Reset hash to force redraw
        this.drawHeatmap(); // Only redraw canvas, not full render
      }
    });

    // Responsive canvas: set up ResizeObserver
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
    }
    const container = this.shadowRoot.querySelector(".canvas-container");
    const canvas = this.shadowRoot.getElementById("heatmapCanvas");
    const setCanvasSize = () => {
      if (!container || !canvas) return;
      const rect = container.getBoundingClientRect();
      // Set canvas size to match container (device pixels)
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      // Trigger redraw using requestAnimationFrame instead of direct call
      if (this._pendingData) {
        if (this._animationFrameId)
          cancelAnimationFrame(this._animationFrameId);
        this._animationFrameId = requestAnimationFrame(() =>
          this.drawHeatmap(),
        );
      }
    };
    this._resizeObserver = new ResizeObserver(setCanvasSize);
    this._resizeObserver.observe(container);

    this._renderInProgress = false;
    // Draw immediately with initial data if available
    if (this._pendingData) {
      this.drawHeatmap();
    }
  }

  async drawHeatmap() {
    const canvas = this.shadowRoot.getElementById("heatmapCanvas");
    const statsEl = this.shadowRoot.getElementById("stats");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0); // reset transform
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#1a1a1a";
    ctx.fillRect(0, 0, width, height);
    // Use _pendingData instead of fetching new data - avoids extra renders
    const data = this._pendingData;
    if (!data || !data.heatmap) {
      ctx.fillStyle = "#999";
      ctx.font = `${Math.max(16, Math.round(height / 25))}px sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText("No heatmap data", width / 2, height / 2);
      if (statsEl) statsEl.textContent = "No heatmap data available";
      return;
    }
    let gridSize = this._config.grid_size;
    let scale = Math.min(width / gridSize, height / gridSize) * 0.9;
    let actualGridHeight = gridSize; // For calculating origin positioning

    // If floorplan is provided and has dimensions metadata, scale according to floorplan
    if (this._floorplanImage && this._config.floorplan_width_mm) {
      const floorplanPhysicalWidth = this._config.floorplan_width_mm;
      const floorplanPhysicalHeight =
        this._config.floorplan_height_mm ||
        (this._floorplanImage.height / this._floorplanImage.width) *
          floorplanPhysicalWidth;

      gridSize = floorplanPhysicalWidth;
      actualGridHeight = floorplanPhysicalHeight;

      // Calculate scale based on canvas and floorplan dimensions
      const canvasAspect = width / height;
      const floorplanAspect = floorplanPhysicalWidth / floorplanPhysicalHeight;

      let scale_x = (width * 0.9) / floorplanPhysicalWidth;
      let scale_y = (height * 0.9) / floorplanPhysicalHeight;

      // Use the smaller scale to fit the entire floorplan
      scale = Math.min(scale_x, scale_y);
    }

    // Origin at lower-left corner (0,0 = lower-left, not center)
    const originX = width * 0.05; // 5% margin from left
    const originY = height * 0.95; // 5% margin from bottom

    const toCanvas = (x, y) => ({
      x: originX + (x + this._config.offset_x) * scale,
      y: originY - (y + this._config.offset_y) * scale, // Invert Y for canvas
    });

    // Draw floorplan background if provided (maintain aspect ratio)
    if (this._floorplanImage) {
      const imgWidth = this._floorplanImage.width;
      const imgHeight = this._floorplanImage.height;
      const imgAspect = imgWidth / imgHeight;
      const canvasAspect = width / height;
      let drawWidth, drawHeight, drawX, drawY;

      if (imgAspect > canvasAspect) {
        // Image is wider, fit to height
        drawHeight = height;
        drawWidth = drawHeight * imgAspect;
      } else {
        // Image is taller, fit to width
        drawWidth = width;
        drawHeight = drawWidth / imgAspect;
      }

      // Center the image
      drawX = (width - drawWidth) / 2;
      drawY = (height - drawHeight) / 2;

      ctx.drawImage(this._floorplanImage, drawX, drawY, drawWidth, drawHeight);
    }

    const heatmapData = data.heatmap;
    const timeline =
      this._heatmapScale === "hourly"
        ? heatmapData.hourly
        : this._heatmapScale === "24h"
          ? heatmapData["24h"]
          : heatmapData.all_time;
    const entries = Object.entries(timeline || {});
    if (entries.length > 0) {
      let maxCount = 0;
      entries.forEach(([k, v]) => {
        if (v > maxCount) maxCount = v;
      });
      ctx.save();
      // Set global opacity only for heatmap overlay (convert percentage to decimal)
      ctx.globalAlpha = this._config.opacity / 100;
      ctx.globalCompositeOperation = "source-over";
      entries.forEach(([k, v]) => {
        const parts = k.split("_");
        const xi = parseInt(parts[0], 10);
        const yi = parseInt(parts[1], 10);
        const RES_MM = heatmapData.resolution_mm || 500;
        const cx_mm = (xi + 0.5) * RES_MM;
        const cy_mm = (yi + 0.5) * RES_MM;
        const cpos = toCanvas(cx_mm, cy_mm);
        const size = RES_MM * scale;
        const intensity = Math.min(1, v / Math.max(1, maxCount));
        const hue = (1 - intensity) * 120;
        // Use intensity only for color (green to red), opacity is controlled by global alpha
        ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
        ctx.fillRect(cpos.x - size / 2, cpos.y - size / 2, size, size);
      });
      ctx.restore();
    }
    if (statsEl) {
      statsEl.textContent = `Heatmap bins: ${entries.length}`;
    }
  }

  disconnectedCallback() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
  }

  async getFloorData() {
    try {
      const configEntryId = await this.discoverConfigEntry();
      if (!configEntryId) return null;
      const result = await this._hass.callWS({
        type: "call_service",
        domain: "radar_fusion",
        service: "get_floor_data",
        service_data: {
          config_entry_id: configEntryId,
          floor_id: this._config.floor_id || null,
        },
        return_response: true,
      });
      return result.response;
    } catch (error) {
      return null;
    }
  }

  async resetHeatmap() {
    try {
      const configEntryId = await this.discoverConfigEntry();
      if (!configEntryId) return null;
      await this._hass.callWS({
        type: "call_service",
        domain: "radar_fusion",
        service: "reset_heatmap",
        service_data: {
          config_entry_id: configEntryId,
          floor_id: this._config.floor_id || null,
        },
      });
      return true;
    } catch (err) {
      return false;
    }
  }

  renderError(message) {
    this.shadowRoot.innerHTML = `
      <style>
        .error-container { padding: 16px; text-align: center; }
        .error-title { color: var(--error-color); font-size: 18px; margin-bottom: 12px; }
        .error-message { color: var(--secondary-text-color); font-size: 14px; margin-bottom: 8px; }
        .error-help { color: var(--primary-color); font-size: 12px; margin-top: 16px; }
      </style>
      <div class="error-container">
        <div class="error-title">⚠️ Radar Fusion Heatmap</div>
        <div class="error-message">${message}</div>
        <div class="error-help">
          💡 Make sure the integration is installed and configured<br>
          Settings → Devices & Services → Add Integration → Radar Fusion
        </div>
      </div>
    `;
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("radar-fusion-heatmap-card-editor");
  }

  static getStubConfig() {
    return {
      config_entry_id: "",
      title: "Radar Heatmap",
    };
  }
}

// Configuration editor for the visual card editor
class RadarFusionHeatmapCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = { ...config };
    this.render();
    this.attachEventListeners();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
        }
        .form-group {
          margin-bottom: 16px;
        }
        label {
          display: block;
          margin-bottom: 8px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        input[type="text"],
        input[type="number"] {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          font-size: 14px;
          box-sizing: border-box;
          background: var(--card-background-color);
          color: var(--primary-text-color);
        }
        input:focus {
          outline: none;
          border-color: var(--primary-color);
        }
        .form-description {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-top: 4px;
        }
        input[type="checkbox"] {
          margin-right: 8px;
          cursor: pointer;
        }
        .checkbox-group {
          display: flex;
          align-items: center;
          margin-top: 8px;
        }
        .checkbox-group label {
          margin: 0;
          font-weight: normal;
        }
      </style>
      <div class="form-group">
        <label for="config_entry_id">Config Entry ID *</label>
        <input
          type="text"
          id="config_entry_id"
          placeholder="Config entry ID from Settings"
          value="${this._config.config_entry_id || ""}"
        />
        <div class="form-description">
          Find this in Settings → Devices & Services → Radar Fusion
        </div>
      </div>

      <div class="form-group">
        <label for="title">Title</label>
        <input
          type="text"
          id="title"
          placeholder="Radar Fusion Heatmap"
          value="${this._config.title || "Radar Fusion Heatmap"}"
        />
      </div>

      <div class="form-group">
        <label for="floor_id">Floor ID</label>
        <input
          type="text"
          id="floor_id"
          placeholder="Optional - leave empty for all floors"
          value="${this._config.floor_id || ""}"
        />
        <div class="form-description">
          Filter to show only a specific floor (e.g., "ground_floor", "first_floor")
        </div>
      </div>

      <div class="form-group">
        <label for="floorplan_url">Floorplan Image URL</label>
        <input
          type="text"
          id="floorplan_url"
          placeholder="/local/floorplan.png"
          value="${this._config.floorplan_url || ""}"
        />
        <div class="form-description">
          Path to your floorplan image (upload via Media browser)
        </div>
      </div>

      <div class="form-group">
        <label for="floorplan_width_mm">Floorplan Width (mm)</label>
        <input
          type="number"
          id="floorplan_width_mm"
          placeholder="10000"
          min="0"
          step="100"
          value="${this._config.floorplan_width_mm || ""}"
        />
        <div class="form-description">
          Physical width of your floorplan in millimeters
        </div>
      </div>

      <div class="form-group">
        <label for="floorplan_height_mm">Floorplan Height (mm)</label>
        <input
          type="number"
          id="floorplan_height_mm"
          placeholder="8000"
          min="0"
          step="100"
          value="${this._config.floorplan_height_mm || ""}"
        />
        <div class="form-description">
          Physical height of your floorplan in millimeters
        </div>
      </div>

      <div class="form-group">
        <label for="offset_x">X Offset (mm)</label>
        <input
          type="number"
          id="offset_x"
          placeholder="0"
          step="10"
          value="${this._config.offset_x || 0}"
        />
        <div class="form-description">
          Horizontal offset to align radar coordinates with floorplan
        </div>
      </div>

      <div class="form-group">
        <label for="offset_y">Y Offset (mm)</label>
        <input
          type="number"
          id="offset_y"
          placeholder="0"
          step="10"
          value="${this._config.offset_y || 0}"
        />
        <div class="form-description">
          Vertical offset to align radar coordinates with floorplan
        </div>
      </div>

      <div class="form-group">
        <label for="width">Width (pixels)</label>
        <input
          type="number"
          id="width"
          min="300"
          max="2000"
          step="100"
          value="${this._config.width || 800}"
        />
      </div>

      <div class="form-group">
        <label for="height">Height (pixels)</label>
        <input
          type="number"
          id="height"
          min="200"
          max="1500"
          step="100"
          value="${this._config.height || 600}"
        />
      </div>

      <div class="form-group">
        <label for="grid_size">Grid Size (mm)</label>
        <input
          type="number"
          id="grid_size"
          min="1000"
          max="20000"
          step="500"
          value="${this._config.grid_size || 5000}"
        />
      </div>

      <div class="form-group">
        <label for="opacity">Heatmap Opacity</label>
        <input
          type="number"
          id="opacity"
          min="0"
          max="100"
          step="5"
          value="${this._config.opacity !== undefined ? this._config.opacity : 50}"
        />
        <div class="form-description">
          Transparency of heatmap overlay (0% = transparent, 100% = opaque)
        </div>
      </div>

      <div class="form-group">
        <div class="checkbox-group">
          <input
            type="checkbox"
            id="show_header"
            ${this._config.show_header !== false ? "checked" : ""}
          />
          <label for="show_header">Show Header</label>
        </div>
        <div class="form-description">
          Display title and heatmap scale controls
        </div>
      </div>

      <div class="form-group">
        <div class="checkbox-group">
          <input
            type="checkbox"
            id="show_legend"
            ${this._config.show_legend !== false ? "checked" : ""}
          />
          <label for="show_legend">Show Legend</label>
        </div>
        <div class="form-description">
          Display statistics at the bottom
        </div>
      </div>

      <div class="form-group">
        <div class="checkbox-group">
          <input
            type="checkbox"
            id="show_grid"
            ${this._config.show_grid ? "checked" : ""}
          />
          <label for="show_grid">Show Grid</label>
        </div>
      </div>
    `;
  }

  attachEventListeners() {
    const inputs = this.shadowRoot.querySelectorAll("input");
    inputs.forEach((input) => {
      input.addEventListener("change", (ev) => this.handleInputChange(ev));
    });
  }

  handleInputChange(ev) {
    const target = ev.target;
    const id = target.id;
    let value;

    if (target.type === "checkbox") {
      value = target.checked;
    } else if (target.type === "number") {
      value = parseInt(target.value, 10);
    } else {
      value = target.value;
    }

    this._config = { ...this._config, [id]: value };
    this.fireConfigChanged();
  }

  fireConfigChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

customElements.define(
  "radar-fusion-heatmap-card-editor",
  RadarFusionHeatmapCardEditor,
);
customElements.define("radar-fusion-heatmap-card", RadarFusionHeatmapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "radar-fusion-heatmap-card",
  name: "Radar Fusion Heatmap Card",
  description: "Standalone heatmap visualization for Radar Fusion",
  preview: true,
  configElement: "radar-fusion-heatmap-card-editor",
});

console.info(
  "%c RADAR-FUSION-HEATMAP-CARD %c v1.0.0 ",
  "color: white; background: #4CAF50; font-weight: bold;",
  "color: #4CAF50; background: white; font-weight: bold;",
);
