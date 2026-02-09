from dataclasses import dataclass

SLEEVE_CAPACITY = {
    1.5: 40,
    3.0: 40,
    6.0: 25,
}


@dataclass(frozen=True)
class PopcornCalcInput:
    bucket_size: float
    yesterday_end: int
    warehouse_morning: int
    sleeves_taken: int
    sold_cashier: int
    tz_left: int


@dataclass(frozen=True)
class PopcornCalcResult:
    brought_buckets: int
    warehouse_after_take: int
    end_of_day: int
    cashier_expected: int
    delta: int



def calculate(data: PopcornCalcInput) -> PopcornCalcResult:
    if data.bucket_size not in SLEEVE_CAPACITY:
        raise ValueError("Unsupported bucket size")

    brought = data.sleeves_taken * SLEEVE_CAPACITY[data.bucket_size]
    warehouse_after = data.warehouse_morning - brought
    end_of_day = warehouse_after + data.tz_left
    cashier_expected = data.yesterday_end - end_of_day
    delta = data.sold_cashier - cashier_expected

    return PopcornCalcResult(
        brought_buckets=brought,
        warehouse_after_take=warehouse_after,
        end_of_day=end_of_day,
        cashier_expected=cashier_expected,
        delta=delta,
    )
