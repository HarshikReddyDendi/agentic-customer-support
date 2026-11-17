import hashlib
import os

import requests
import streamlit as st


st.set_page_config(
    page_title="Customer Support Assistant",
    page_icon="S",
    layout="wide",
)


def _request(
    method: str,
    api_base_url: str,
    path: str,
    token: str,
    json_body: dict[str, object] | None = None,
) -> dict[str, object] | list[object]:
    response = requests.request(
        method,
        f"{api_base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        json=json_body,
    )
    response.raise_for_status()
    return response.json()


def _load_history(
    api_base_url: str,
    customer_id: int,
    token: str,
) -> list[dict[str, object]]:
    history = _request(
        "GET",
        api_base_url,
        f"/chat/history/{customer_id}",
        token,
    )
    if not isinstance(history, dict):
        raise ValueError("The API returned an invalid conversation history")
    messages = history.get("messages")
    if not isinstance(messages, list):
        raise ValueError("The API response did not contain a message list")
    return [message for message in messages if isinstance(message, dict)]


st.title("Customer Support Assistant")
st.caption("Ask a question, check an order, or review your support tickets.")

with st.sidebar:
    st.header("Customer connection")
    api_base_url = st.text_input(
        "API base URL",
        value=os.getenv("SUPPORT_API_URL", "http://127.0.0.1:8000"),
    ).strip()
    customer_id = st.number_input("Customer ID", min_value=1, step=1)
    token = st.text_input(
        "Customer access token",
        type="password",
        help="Request a short-lived access token from your support administrator.",
    ).strip()

if not api_base_url or not token or customer_id < 1:
    st.info("Enter your customer ID and access token in the sidebar to continue.")
    st.stop()

customer_id = int(customer_id)
token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
history_key = (api_base_url, customer_id, token_fingerprint)

if st.session_state.get("history_key") != history_key:
    try:
        st.session_state["messages"] = _load_history(
            api_base_url,
            customer_id,
            token,
        )
        st.session_state["history_key"] = history_key
    except requests.RequestException as error:
        st.error(f"Could not load conversation history: {error}")
        st.stop()
    except ValueError as error:
        st.error(str(error))
        st.stop()

left_column, right_column = st.columns([2, 1], gap="large")

with left_column:
    st.subheader("Conversation")
    for message in st.session_state.get("messages", []):
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        with st.chat_message(role):
            st.write(message.get("content", ""))
            sources = message.get("sources", [])
            if role == "assistant" and isinstance(sources, list) and sources:
                st.caption("Sources: " + ", ".join(str(source) for source in sources))
            if role == "assistant" and message.get("needs_human"):
                st.warning("This conversation has been referred to human support.")

    customer_message = st.chat_input("How can we help?")
    if customer_message:
        with st.spinner("Checking support information..."):
            try:
                result = _request(
                    "POST",
                    api_base_url,
                    "/chat",
                    token,
                    json_body={"message": customer_message},
                )
                if not isinstance(result, dict):
                    raise ValueError("The API returned an invalid chat response")
            except requests.RequestException as error:
                st.error(f"Could not send your message: {error}")
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["messages"].extend(
                    [
                        {"role": "user", "content": customer_message},
                        {
                            "role": "assistant",
                            "content": result.get("answer", ""),
                            "sources": result.get("sources", []),
                            "needs_human": result.get("needs_human", False),
                        },
                    ]
                )
                st.rerun()

with right_column:
    st.subheader("Order lookup")
    order_id = st.number_input(
        "Order ID",
        min_value=1,
        step=1,
        key="order_lookup_id",
    )
    if st.button("Check order"):
        with st.spinner("Looking up your order..."):
            try:
                order = _request(
                    "GET",
                    api_base_url,
                    f"/orders/{int(order_id)}",
                    token,
                )
                if not isinstance(order, dict):
                    raise ValueError("The API returned an invalid order response")
                st.success(
                    f"Order {order.get('id')}: {order.get('product')} — "
                    f"{order.get('status')}"
                )
            except requests.RequestException as error:
                st.error(f"Could not look up that order: {error}")
            except ValueError as error:
                st.error(str(error))

    st.subheader("Your support tickets")
    with st.expander("Create a support ticket", expanded=False):
        ticket_issue = st.text_area("Issue description", max_chars=500)
        ticket_priority = st.selectbox(
            "Priority",
            options=["Low", "Medium", "High"],
            index=1,
        )
        if st.button("Submit ticket"):
            if not ticket_issue.strip():
                st.error("Enter an issue description.")
            else:
                try:
                    ticket = _request(
                        "POST",
                        api_base_url,
                        "/tickets",
                        token,
                        json_body={
                            "customer_id": customer_id,
                            "issue": ticket_issue.strip(),
                            "priority": ticket_priority,
                        },
                    )
                    if not isinstance(ticket, dict):
                        raise ValueError("The API returned an invalid ticket")
                    st.success(f"Created ticket #{ticket.get('id')}")
                except requests.RequestException as error:
                    st.error(f"Could not create the ticket: {error}")
                except ValueError as error:
                    st.error(str(error))

    if st.button("Refresh tickets"):
        try:
            tickets = _request("GET", api_base_url, "/tickets", token)
            if not isinstance(tickets, list):
                raise ValueError("The API returned an invalid ticket list")
            if not tickets:
                st.info("You do not have any support tickets yet.")
            for ticket in tickets:
                if isinstance(ticket, dict):
                    with st.container(border=True):
                        st.write(f"Ticket #{ticket.get('id')}")
                        st.write(ticket.get("issue", ""))
                        st.caption(
                            f"Status: {ticket.get('status')} · "
                            f"Priority: {ticket.get('priority')}"
                        )
        except requests.RequestException as error:
            st.error(f"Could not load your tickets: {error}")
        except ValueError as error:
            st.error(str(error))

    st.subheader("Human support status")
    if st.button("Refresh escalation status"):
        try:
            escalations = _request(
                "GET",
                api_base_url,
                "/escalations",
                token,
            )
            if not isinstance(escalations, list):
                raise ValueError("The API returned an invalid escalation list")
            if not escalations:
                st.info("There are no human support requests.")
            for escalation in escalations:
                if isinstance(escalation, dict):
                    with st.container(border=True):
                        st.write(f"Escalation #{escalation.get('id')}")
                        st.write(escalation.get("reason", "Human support requested"))
                        st.caption(f"Status: {escalation.get('status')}")
        except requests.RequestException as error:
            st.error(f"Could not load escalation status: {error}")
        except ValueError as error:
            st.error(str(error))
