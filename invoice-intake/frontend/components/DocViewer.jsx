"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { findEvidence } from "../lib/evidence";

function norm(n) {
  return `${n * 100}%`;
}

export default function DocViewer({ pages, tokens = [], highlight, docLabel }) {
  const imgs = Array.isArray(pages) ? pages : [];
  const [page, setPage] = useState(0);
  const [scale, setScale] = useState(1);
  const [fit, setFit] = useState(true);
  const [rotate, setRotate] = useState(0);
  const [natW, setNatW] = useState(0);
  const [natH, setNatH] = useState(0);
  const [dragging, setDragging] = useState(null);
  const stageRef = useRef(null);
  const imgRef = useRef(null);

  const current = imgs[Math.min(page, Math.max(0, imgs.length - 1))] || null;

  const effScale = fit && natW ? Math.min(3, Math.max(0.2, scale)) : scale;

  useEffect(() => {
    setPage(0);
  }, [pages]);

  useEffect(() => {
    if (!current) return;
    const img = new Image();
    img.onload = () => {
      setNatW(img.naturalWidth || 1);
      setNatH(img.naturalHeight || 1);
    };
    img.src = current.url;
  }, [current]);

  const fitScale = useCallback(() => {
    if (!stageRef.current || !natW) return 1;
    const avail = stageRef.current.clientWidth - 48;
    return Math.min(2, Math.max(0.2, avail / natW));
  }, [natW]);

  const zoomBy = (factor) => {
    const base = fit && natW ? fitScale() : scale;
    setFit(false);
    setScale(Math.min(4, Math.max(0.2, base * factor)));
  };

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (e) => {
      if (e.deltaY === 0) return;
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const base = fit && natW ? fitScale() : scale;
      setFit(false);
      setScale(Math.min(4, Math.max(0.2, base * (e.deltaY < 0 ? 1.12 : 0.89))));
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [fit, scale, natW, fitScale]);

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    setDragging({ x: e.clientX, y: e.clientY });
  };
  const onMouseMove = (e) => {
    if (!dragging || !stageRef.current) return;
    const stage = stageRef.current;
    stage.scrollLeft -= e.clientX - dragging.x;
    stage.scrollTop -= e.clientY - dragging.y;
    setDragging({ x: e.clientX, y: e.clientY });
  };
  const endDrag = () => setDragging(null);

  const match = highlight ? findEvidence(tokens, highlight.value) : null;
  const hlBoxes = match?.boxes || [];

  const goto = (i) => setPage((p) => Math.min(imgs.length - 1, Math.max(0, i)));

  const cssRotate = { transform: `rotate(${rotate}deg)` };
  const imgWidth = fit && natW ? "100%" : natW ? `${Math.round(natW * scale)}px` : "auto";
  const wrapperStyle = fit && natW ? { width: `${fitScale() * 100}%` } : { width: imgWidth };

  return (
    <div className="docviewer">
      <div className="docviewer-toolbar">
        {imgs.length > 1 && (
          <>
            <button className="btn btn-xs btn-soft" onClick={() => goto(page - 1)} disabled={page === 0}>
              Previous
            </button>
            <span className="t-caption-sm muted nowrap">
              Page {page + 1} / {imgs.length}
            </span>
            <button className="btn btn-xs btn-soft" onClick={() => goto(page + 1)} disabled={page === imgs.length - 1}>
              Next
            </button>
            <span className="divider" style={{ width: 1, height: 22, margin: "0 4px" }} />
          </>
        )}
        <button className="btn btn-xs btn-circle" title="Zoom out (Ctrl+scroll to zoom)" onClick={() => zoomBy(0.85)}>−</button>
        <span className="t-caption" style={{ minWidth: 46, textAlign: "center" }}>
          {fit ? "Fit" : `${Math.round(effScale * 100)}%`}
        </span>
        <button className="btn btn-xs btn-circle" title="Zoom in" onClick={() => zoomBy(1.18)}>+</button>
        <button className="btn btn-xs btn-soft" onClick={() => { setFit(true); setScale(1); }}>
          Fit to screen
        </button>
        <button className="btn btn-xs btn-soft" onClick={() => setRotate((r) => (r + 90) % 360)}>
          Rotate
        </button>
        <span className="grow" />
      </div>

      <div
        className="docviewer-stage"
        ref={stageRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        style={{ cursor: dragging ? "grabbing" : "grab" }}
      >
        {!current ? (
          <div className="viewer-msg">
            <div className="spin" />
            <span>Loading document…</span>
          </div>
        ) : (
          <div className={fit ? "page-canvas mode-scaled" : "page-canvas"} style={{ ...wrapperStyle, ...cssRotate }} ref={imgRef}>
            <img
              src={current.url}
              alt={docLabel || "Invoice document"}
              draggable={false}
              style={{ width: imgWidth }}
            />
            {hlBoxes.map((b, i) => {
              const padX = b.w * 0.5;
              const padY = b.h * 0.5;
              return (
                <span
                  key={`${b.page}-${i}`}
                  className={match?.exact ? "hl-box actual" : "hl-box"}
                  style={{
                    left: norm(b.x - padX),
                    top: norm(b.y - padY),
                    width: norm(b.w + padX * 2),
                    height: norm(b.h + padY * 2),
                    visibility: b.page === page + 1 ? "visible" : "hidden",
                  }}
                />
              );
            })}
            {highlight && (
              <div className="fit-tag">
                {match?.matched ? (
                  <>
                    <span style={{ color: "#7ef0b2" }}>✓</span>
                    <span>Source: {highlight.label}</span>
                    <span style={{ opacity: 0.85 }}>「{highlight.value}」</span>
                    {match.fuzzy && <span style={{ opacity: 0.7 }}>(partial match)</span>}
                  </>
                ) : (
                  <span style={{ opacity: 0.85 }}>
                    Source not found for {highlight.label} —「{highlight.value}」scroll the document to compare.
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}