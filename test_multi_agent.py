from orchestrator.orchestrator import (
    ProductivitySupervisor
)

def main():

    orchestrator = ProductivitySupervisor()

    print()
    print("=" * 50)
    print(" MULTI-AGENT PRODUCTIVITY SYSTEM")
    print("=" * 50)

    print()
    print("Type 'exit' to stop.")

    while True:

        user = input("\nYou: ").strip()

        if user.lower() == "exit":

            print("Goodbye!")

            break

        if not user:
            continue

        try:

            result = orchestrator.run(
                user
            )

            print("\nResult:")

            print(result)

        except Exception as e:

            print(
                f"\n[ERROR] {e}"
            )

if __name__ == "__main__":
    main()