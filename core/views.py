from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta
from .models import DeliveryInfo, Stops, RouteInfo, Trip
from django.utils import timezone
from datetime import timezone as tz
from decouple import config
import openrouteservice
from collections import defaultdict

ORS_API_KEY = config("ORS_API_KEY")

class PlanTripView(APIView):
    def post(self, request):
        data = request.data
        cl, pu, do = data['current_location'], data['pickup_location'], data['dropoff_location']
        current_used = float(data['current_used_cycle'])

        PICKUP_T = DROPOFF_T = timedelta(hours=1)
        FUEL_STOP_DIST = 1000
        FUEL_STOP_DURATION = timedelta(minutes=15)
        RESET_HOURS = 34
        FULL_CYCLE = 70.0
        AVG_SPEED = 50

        coords = [[cl['lon'], cl['lat']], [pu['lon'], pu['lat']], [do['lon'], do['lat']]]
        ors_client = openrouteservice.Client(key=ORS_API_KEY)
        directions = ors_client.directions(
            coordinates=coords,
            profile='driving-car',
            format='geojson',
            units='mi'
        )

        geometry = directions['features'][0]['geometry']['coordinates']
        route_props = directions['features'][0]['properties']['segments'][0]
        total_dist = route_props['distance']
        total_time = route_props['duration']
        total_hours = total_time / 3600

        start_time = timezone.now()
        current_time = start_time
        remaining_cycle = FULL_CYCLE - current_used

        trip = Trip.objects.create(
            trip_start_date=start_time, current_used_cycle=current_used,
            delivery_info=DeliveryInfo.objects.create(
                current_location_lat=cl['lat'], current_location_lon=cl['lon'],
                pickup_location_lat=pu['lat'], pickup_location_lon=pu['lon'],
                dropoff_location_lat=do['lat'], dropoff_location_lon=do['lon'],
                time_to_pickup=PICKUP_T, time_to_dropoff=current_time + timedelta(hours=total_hours)
            )
        )

        route_info = RouteInfo.objects.create(
            start_time=start_time, end_time=current_time + timedelta(hours=total_hours),
            start_location_lat=cl['lat'], start_location_lon=cl['lon'],
            end_location_lat=do['lat'], end_location_lon=do['lon'],
            remaining_cycle=remaining_cycle, status="DRIVING"
        )

        stops_data = []

        def log_stop(status, duration, lat, lon, remark):
            nonlocal current_time, remaining_cycle
            stop = Stops.objects.create(
                start_time=current_time,
                end_time=current_time + duration,
                status=status,
                remark=remark,
                location_lat=lat,
                location_lon=lon
            )
            route_info.stops.add(stop)
            stops_data.append(stop)
            current_time += duration

            hrs = duration.total_seconds() / 3600
            if status in ['DRIVING', 'ON_DUTY']:
                remaining_cycle = max(0.0, remaining_cycle - hrs)
            if status in ['OFF_DUTY', 'SLEEPER_BERTH'] and hrs >= RESET_HOURS:
                remaining_cycle = FULL_CYCLE
            return stop

        log_stop("ON_DUTY", PICKUP_T, pu['lat'], pu['lon'], "Pickup cargo")

        miles = 0.0
        leg = 1
        i = 0
        daily_drive_time = 0.0
        daily_shift_time = 0.0
        last_rest_time = current_time

        while i < len(geometry) - 1:
            max_leg_drive_time = min(11 - daily_drive_time, 14 - daily_shift_time, remaining_cycle, 8)
            if max_leg_drive_time <= 0:
                lat, lon = geometry[i][1], geometry[i][0]
                log_stop("SLEEPER_BERTH", timedelta(hours=10), lat, lon, "10-hour mandatory rest")
                daily_drive_time = 0.0
                daily_shift_time = 0.0
                last_rest_time = current_time
                continue

            drive_hours = max_leg_drive_time
            drive_miles = drive_hours * AVG_SPEED
            drive_dur = timedelta(hours=drive_hours)

            segment_miles = 0
            while i < len(geometry) - 1 and segment_miles < drive_miles:
                lat1, lon1 = geometry[i][1], geometry[i][0]
                lat2, lon2 = geometry[i + 1][1], geometry[i + 1][0]
                d = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5 * 69
                segment_miles += d
                i += 1

            miles += segment_miles
            lat, lon = geometry[i][1], geometry[i][0]
            log_stop("DRIVING", drive_dur, lat, lon, f"Driving leg {leg}")
            daily_drive_time += drive_hours
            daily_shift_time += drive_hours
            leg += 1

            if (current_time - last_rest_time).total_seconds() / 3600 >= 8:
                log_stop("OFF_DUTY", timedelta(minutes=30), lat, lon, "30-min rest after 8 hours")
                last_rest_time = current_time
                daily_shift_time += 0.5

            if miles < total_dist and miles % FUEL_STOP_DIST < AVG_SPEED:
                log_stop("ON_DUTY", FUEL_STOP_DURATION, lat, lon, "Fuel stop")
                daily_shift_time += FUEL_STOP_DURATION.total_seconds() / 3600

            if remaining_cycle <= 0.1:
                log_stop("SLEEPER_BERTH", timedelta(hours=34), lat, lon, "Cycle reset (34-hour rest)")
                remaining_cycle = FULL_CYCLE
                daily_drive_time = 0.0
                daily_shift_time = 0.0
                last_rest_time = current_time

        log_stop("ON_DUTY", DROPOFF_T, do['lat'], do['lon'], "Drop-off cargo")

        route_info.remaining_cycle = remaining_cycle
        route_info.save()
        trip.route_info.add(route_info)

        return Response({
            "trip_id": trip.id,
            "total_hours": total_hours,
            "remaining_cycle": remaining_cycle,
            "route_plan": [
                {
                    "status": s.status,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "lat": s.location_lat,
                    "lon": s.location_lon,
                    "remark": s.remark
                }
                for s in stops_data
            ]
        }, status=status.HTTP_201_CREATED)


class TripRouteLogsView(APIView):
    def get(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found."}, status=status.HTTP_404_NOT_FOUND)

        # Group logs by date (e.g. "2025-08-01")
        daily_logs = defaultdict(list)
        
        for route in trip.route_info.all():
            for stop in route.stops.all().order_by("start_time"):
                day = stop.start_time.astimezone(tz.utc).date().isoformat()
                daily_logs[day].append({
                    "status": stop.status,
                    "start_time": stop.start_time.isoformat(),
                    "end_time": stop.end_time.isoformat(),
                    "lat": float(stop.location_lat),
                    "lon": float(stop.location_lon),
                    "remark": stop.remark
                })

        # Format into a normal dict
        sorted_logs = dict(sorted(daily_logs.items()))

        return Response({
            "trip_id": trip.id,
            "trip_start_date": trip.trip_start_date.isoformat(),
            "daily_logs": sorted_logs
        }, status=status.HTTP_200_OK)

