import importlib


def main():
    module = importlib.import_module("rag.chain")
    assert hasattr(module, "invoke")
    assert hasattr(module, "get_chain")
    print("RAG chain import test passed")


if __name__ == "__main__":
    main()
