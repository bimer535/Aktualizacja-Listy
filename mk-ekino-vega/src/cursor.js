/* Manual TV pointer geometry; no document inspection or automatic clicks. GPL-3.0-only. */
'use strict';
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
function movePointer(point, direction, bounds) {
  const dx = 16 / Math.max(1, bounds.width), dy = 16 / Math.max(1, bounds.height);
  return {x:clamp(point.x + (direction === 'left' ? -dx : direction === 'right' ? dx : 0),0,1),
    y:clamp(point.y + (direction === 'up' ? -dy : direction === 'down' ? dy : 0),0,1)};
}
function touchPoint(point, viewport) {
  if (!viewport || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height) ||
      viewport.width < 2 || viewport.height < 2 || viewport.width > 16384 || viewport.height > 16384) {
    throw Error('viewport-unavailable');
  }
  // client coordinates are relative to the visible viewport, not page offsets.
  return {clientX:clamp(Math.round(point.x * viewport.width),1,viewport.width-1),
    clientY:clamp(Math.round(point.y * viewport.height),1,viewport.height-1)};
}
module.exports = {movePointer,touchPoint};
