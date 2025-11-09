/**
 * Convert backend trip response to frontend format
 */

import { TripResponse as BackendTripResponse, Day as BackendDay, TimeBlock, POI } from '../services/api';

export interface FrontendTrip {
  trip_id: string;
  status: 'processing' | 'completed' | 'failed';
  city: string;
  origin: string;
  start_date: string;
  end_date: string;
  days: FrontendDay[];
  booking_links: {
    flights: string;
    hotels: string;
  };
}

export interface FrontendDay {
  date: string;
  activities: FrontendActivity[];
}

export interface FrontendActivity {
  time: string;
  name: string;
  type: 'attraction' | 'food';
  lat: number;
  lon: number;
  duration_min: number;
  booking_required?: boolean;
  booking_url?: string;  // Changed from string | null to match existing Trip type
  notes?: string;  // Changed from string | null to match existing Trip type
}

/**
 * Determine activity type based on POI tags
 */
function getActivityType(poi: POI): 'attraction' | 'food' {
  const tags = poi.tags.map(t => t.toLowerCase());
  
  // Check if it's food-related
  if (tags.some(tag => 
    tag.includes('food') || 
    tag.includes('restaurant') || 
    tag.includes('cafe') || 
    tag.includes('pizza') ||
    tag.includes('lunch') ||
    tag.includes('dinner') ||
    poi.name.toLowerCase().includes('lunch')
  )) {
    return 'food';
  }
  
  return 'attraction';
}

/**
 * Convert backend TimeBlock to frontend Activity
 */
function convertTimeBlockToActivity(block: TimeBlock): FrontendActivity {
  return {
    time: block.start_time,
    name: block.poi.name,
    type: getActivityType(block.poi),
    lat: block.poi.lat,
    lon: block.poi.lon,
    duration_min: block.poi.duration_min,
    booking_required: block.poi.booking_required,
    booking_url: block.poi.booking_url || undefined,  // Convert null to undefined
    notes: block.poi.notes || undefined,  // Convert null to undefined
  };
}

/**
 * Convert backend Day to frontend Day
 */
function convertDay(backendDay: BackendDay): FrontendDay {
  // Handle both formats: blocks (internal) and activities (API response)
  if ('blocks' in backendDay && backendDay.blocks) {
    return {
      date: backendDay.date,
      activities: backendDay.blocks.map(convertTimeBlockToActivity),
    };
  } else if ('activities' in backendDay && (backendDay as any).activities) {
    // Already in activities format (from PATCH response)
    return {
      date: backendDay.date,
      activities: (backendDay as any).activities,
    };
  }
  
  // Fallback: empty activities
  return {
    date: backendDay.date,
    activities: [],
  };
}

/**
 * Convert full backend trip response to frontend format
 */
export function convertBackendTripToFrontend(backendTrip: BackendTripResponse): FrontendTrip {
  // Ensure days is an array
  const days = Array.isArray(backendTrip.days) ? backendTrip.days : [];
  
  return {
    trip_id: backendTrip.trip_id,
    status: backendTrip.status,
    city: backendTrip.city,
    origin: backendTrip.origin,
    start_date: backendTrip.start_date,
    end_date: backendTrip.end_date,
    days: days.map(convertDay),
    booking_links: backendTrip.booking_links,
  };
}
