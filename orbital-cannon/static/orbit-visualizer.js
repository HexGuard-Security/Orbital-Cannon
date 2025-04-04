/**
 * Orbital Cannon - Satellite Orbit Visualizer
 * This script provides orbit visualization capabilities for the satellite tracker
 */

class OrbitVisualizer {
    constructor(map) {
        this.map = map;
        this.orbitPath = null;
        this.orbitPoints = [];
        this.footprint = null;
    }

    /**
     * Calculate future positions based on current position and velocity
     * @param {Object} position - Current satellite position data
     * @param {number} minutesAhead - Minutes to predict ahead
     * @param {number} steps - Number of points to generate
     * @returns {Array} Array of predicted positions
     */
    predictOrbit(position, minutesAhead = 120, steps = 100) {
        // Clear previous orbit points
        this.orbitPoints = [];
        
        // Constants
        const earthRadius = 6371.0; // km
        const mu = 3.986004418e14; // Earth's gravitational parameter (m^3/s^2)
        
        // Current position in cartesian coordinates (km)
        const pos = {
            x: position.position_x,
            y: position.position_y,
            z: position.position_z
        };
        
        // Current velocity in cartesian coordinates (km/s)
        const vel = {
            x: position.velocity_x,
            y: position.velocity_y,
            z: position.velocity_z
        };
        
        // Calculate orbital period based on altitude (very approximate)
        const altitude = position.altitude; // km
        const semiMajorAxis = (earthRadius + altitude) * 1000; // m
        const orbitalPeriod = 2 * Math.PI * Math.sqrt(Math.pow(semiMajorAxis, 3) / mu); // seconds
        
        // Get magnitude of position and velocity
        const posMag = Math.sqrt(pos.x * pos.x + pos.y * pos.y + pos.z * pos.z);
        const velMag = Math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z);
        
        // Time step for prediction
        const timeStep = (minutesAhead * 60) / steps; // seconds
        
        // Calculate specific angular momentum vector h = r × v
        const h = {
            x: pos.y * vel.z - pos.z * vel.y,
            y: pos.z * vel.x - pos.x * vel.z,
            z: pos.x * vel.y - pos.y * vel.x
        };
        const hMag = Math.sqrt(h.x * h.x + h.y * h.y + h.z * h.z);
        
        // Calculate eccentricity vector e = (v × h)/μ - r/|r|
        const e = {
            x: ((vel.y * h.z - vel.z * h.y) / (mu / 1000)) - pos.x / posMag,
            y: ((vel.z * h.x - vel.x * h.z) / (mu / 1000)) - pos.y / posMag,
            z: ((vel.x * h.y - vel.y * h.x) / (mu / 1000)) - pos.z / posMag
        };
        const eMag = Math.sqrt(e.x * e.x + e.y * e.y + e.z * e.z);
        
        // Simple orbital propagation (two-body problem approximation)
        for (let i = 0; i <= steps; i++) {
            const t = i * timeStep; // seconds elapsed
            
            // For circular/near-circular orbits, use simple circular approximation
            if (eMag < 0.01) {
                const angle = (t / orbitalPeriod) * 2 * Math.PI; // angle in radians
                
                // Rotate position vector in the orbital plane
                const cosAngle = Math.cos(angle);
                const sinAngle = Math.sin(angle);
                
                // Define rotation matrix around angular momentum vector
                // This is a simplification that works for near-circular orbits
                const newPos = {
                    x: pos.x * cosAngle - pos.y * sinAngle,
                    y: pos.x * sinAngle + pos.y * cosAngle,
                    z: pos.z
                };
                
                // Convert to lat/lon
                const r = Math.sqrt(newPos.x * newPos.x + newPos.y * newPos.y + newPos.z * newPos.z);
                const lat = Math.asin(newPos.z / r) * 180 / Math.PI;
                const lon = Math.atan2(newPos.y, newPos.x) * 180 / Math.PI;
                
                // Add to orbit points
                this.orbitPoints.push([lat, lon]);
            } else {
                // For elliptical orbits, use a more accurate approximation based on Kepler's equation
                // This is beyond the scope of this simple visualizer but would be more accurate
                
                // Instead, we use a simplified approach for demonstration
                const meanMotion = 2 * Math.PI / orbitalPeriod; // radians per second
                const meanAnomaly = meanMotion * t;
                
                // Approximate true anomaly (this is a simplification)
                const trueAnomaly = meanAnomaly + 2 * eMag * Math.sin(meanAnomaly);
                
                // Calculate position in orbital plane (perifocal coordinates)
                const p = (hMag * hMag) / (mu / 1000) * (1 / (1 + eMag * Math.cos(trueAnomaly)));
                const xPeri = p * Math.cos(trueAnomaly);
                const yPeri = p * Math.sin(trueAnomaly);
                
                // Convert back to ECI (simplified)
                // This is a major simplification and would need a proper coordinate transformation
                const newPos = {
                    x: xPeri,
                    y: yPeri,
                    z: 0 // Assuming orbital plane is xy-plane for simplicity
                };
                
                // Convert to lat/lon
                const r = Math.sqrt(newPos.x * newPos.x + newPos.y * newPos.y + newPos.z * newPos.z);
                const lat = Math.asin(newPos.z / r) * 180 / Math.PI;
                const lon = Math.atan2(newPos.y, newPos.x) * 180 / Math.PI;
                
                // Add to orbit points
                this.orbitPoints.push([lat, lon]);
            }
        }
        
        return this.orbitPoints;
    }
    
    /**
     * Draw the orbit path on the map
     * @param {Object} position - Current satellite position
     * @param {string} color - Color of the orbit path
     */
    drawOrbit(position, color = '#9D4EDD') {
        // Remove previous orbit path if exists
        this.clearOrbit();
        
        // Generate orbit prediction
        this.predictOrbit(position);
        
        // Draw orbit path on map
        this.orbitPath = L.polyline(this.orbitPoints, {
            color: color,
            weight: 2,
            opacity: 0.7,
            dashArray: '5, 5'
        }).addTo(this.map);
        
        // Draw satellite footprint (visibility circle)
        this.drawFootprint(position);
    }
    
    /**
     * Draw satellite footprint (visibility area)
     * @param {Object} position - Current satellite position
     */
    drawFootprint(position, color = '#00F5D4') {
        // Remove previous footprint if exists
        if (this.footprint) {
            this.map.removeLayer(this.footprint);
        }
        
        // Calculate footprint radius
        const h = position.altitude; // altitude in km
        const earthRadius = 6371.0; // Earth radius in km
        const theta = Math.acos(earthRadius / (earthRadius + h)); // central angle
        const footprintRadius = earthRadius * Math.sin(theta); // radius in km
        
        // Convert to degrees for the map (very approximate)
        const radiusDegrees = (footprintRadius / earthRadius) * 90;
        
        // Draw footprint
        this.footprint = L.circle([position.latitude, position.longitude], {
            radius: radiusDegrees * 111000, // convert to meters (111km per degree)
            color: color,
            fillColor: color,
            fillOpacity: 0.1,
            weight: 1
        }).addTo(this.map);
    }
    
    /**
     * Clear orbit visualization from map
     */
    clearOrbit() {
        if (this.orbitPath) {
            this.map.removeLayer(this.orbitPath);
        }
        
        if (this.footprint) {
            this.map.removeLayer(this.footprint);
        }
    }
}
