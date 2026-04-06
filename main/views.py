"""
API views for order management.
"""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CreateOrderSerializer, OrderOutputSerializer
from .services import create_order


class CreateOrderView(APIView):
    """
    POST /api/orders/

    Create a new order, optionally applying a promo code.

    Request body
    ------------
    {
        "user_id": 1,
        "goods": [{"good_id": 1, "quantity": 2}],
        "promo_code": "SUMMER2025"   // optional
    }

    Response (201 Created)
    ----------------------
    {
        "user_id": 1,
        "order_id": 1,
        "goods": [{"good_id": 1, "quantity": 2, "price": "100.00",
                   "discount": "0.1000", "total": "180.00"}],
        "price": "200.00",
        "discount": "0.1000",
        "total": "180.00"
    }
    """

    def post(self, request: Request) -> Response:
        in_serializer = CreateOrderSerializer(data=request.data)
        in_serializer.is_valid(raise_exception=True)

        data = in_serializer.validated_data
        order = create_order(
            user_id=data["user_id"],
            goods_input=data["goods"],
            goods_map=data["_goods_map"],
            promo=data.get("_promo"),
        )

        out_serializer = OrderOutputSerializer(order)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)
