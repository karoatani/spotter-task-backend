from django.db import models

HOS_STATUS_CHOICES = [
    ('OFF_DUTY', 'Off Duty'),
    ('SLEEPER_BERTH', 'Sleeper Berth'),
    ('DRIVING', 'Driving'),
    ('ON_DUTY', 'On Duty (Not Driving)'),
]

class DeliveryInfo(models.Model):
    current_location_lat = models.DecimalField(max_digits=9, decimal_places=6)
    current_location_lon = models.DecimalField(max_digits=9, decimal_places=6)

    pickup_location_lat = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_location_lon = models.DecimalField(max_digits=9, decimal_places=6)

    dropoff_location_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_location_lon = models.DecimalField(max_digits=9, decimal_places=6)

    time_to_pickup = models.DurationField()
    time_to_dropoff = models.DateTimeField()

    def __str__(self):
        return f"From ({self.pickup_location_lat}, {self.pickup_location_lon}) to ({self.dropoff_location_lat}, {self.dropoff_location_lon})"

class Stops(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location_lat = models.DecimalField(max_digits=9, decimal_places=6,default=0.0)
    location_lon = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    status = models.CharField(max_length=32, choices=HOS_STATUS_CHOICES)
    remark = models.TextField(blank=True)

    def __str__(self):
        return f"{self.status} from {self.start_time} to {self.end_time}"

class RouteInfo(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    start_location_lat = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    start_location_lon = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    end_location_lat = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    end_location_lon = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    remaining_cycle = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    stops = models.ManyToManyField(Stops)
    status = models.CharField(max_length=32, choices=HOS_STATUS_CHOICES)

    def __str__(self):
        return f"Route from {self.start_time} to {self.end_time} - {self.status}"

class Trip(models.Model):
    trip_start_date = models.DateTimeField()
    delivery_info = models.OneToOneField(DeliveryInfo, on_delete=models.CASCADE)
    current_used_cycle = models.DecimalField(max_digits=5, decimal_places=2)
    route_info = models.ManyToManyField(RouteInfo)

    def __str__(self):
        return f"Trip on {self.trip_start_date}"
