// NYC Graph Database Seed Data
// This file contains Cypher statements to create nodes and relationships for NYC POIs

// Create City node
CREATE (nyc:City {
    name: 'New York City',
    country: 'USA',
    lat: 40.7128,
    lon: -74.0060
});

// Create Neighborhood nodes
CREATE (lower_manhattan:Neighborhood {
    name: 'Lower Manhattan',
    city: 'New York City',
    center_lat: 40.7074,
    center_lon: -74.0113
});

CREATE (midtown:Neighborhood {
    name: 'Midtown',
    city: 'New York City',
    center_lat: 40.7549,
    center_lon: -73.9840
});

// Create POI nodes
CREATE (statue:POI {
    id: 'statue-of-liberty',
    name: 'Statue of Liberty',
    lat: 40.6892,
    lon: -74.0445,
    category: 'landmark',
    popularity: 0.98
});

CREATE (summit:POI {
    id: 'summit-one-vanderbilt',
    name: 'SUMMIT One Vanderbilt',
    lat: 40.7545,
    lon: -73.9790,
    category: 'observation deck',
    popularity: 0.92
});

// Create TicketProvider nodes
CREATE (statue_cruises:TicketProvider {
    name: 'Statue City Cruises',
    url: 'https://www.statuecitycruises.com/',
    booking_type: 'required'
});

CREATE (summit_tickets:TicketProvider {
    name: 'SUMMIT Tickets',
    url: 'https://www.summitov.com/',
    booking_type: 'required'
});

// Create relationships
MATCH (p:POI {id: 'statue-of-liberty'}), (n:Neighborhood {name: 'Lower Manhattan'})
CREATE (p)-[:IN_NEIGHBORHOOD]->(n);

MATCH (p:POI {id: 'summit-one-vanderbilt'}), (n:Neighborhood {name: 'Midtown'})
CREATE (p)-[:IN_NEIGHBORHOOD]->(n);

MATCH (p:POI {id: 'statue-of-liberty'}), (t:TicketProvider {name: 'Statue City Cruises'})
CREATE (p)-[:REQUIRES_TICKET {advance_days: 7}]->(t);

MATCH (p:POI {id: 'summit-one-vanderbilt'}), (t:TicketProvider {name: 'SUMMIT Tickets'})
CREATE (p)-[:REQUIRES_TICKET {advance_days: 1}]->(t);

// Create indexes for performance
CREATE INDEX poi_id_index IF NOT EXISTS FOR (p:POI) ON (p.id);
CREATE INDEX poi_name_index IF NOT EXISTS FOR (p:POI) ON (p.name);
CREATE INDEX neighborhood_name_index IF NOT EXISTS FOR (n:Neighborhood) ON (n.name);
CREATE INDEX city_name_index IF NOT EXISTS FOR (c:City) ON (c.name);
