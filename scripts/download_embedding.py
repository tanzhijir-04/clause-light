"""下载 embedding 模型（首次运行时执行）"""

from sentence_transformers import SentenceTransformer


def main():
    model_name = "shibing624/text2vec-base-chinese"
    print(f"正在下载 embedding 模型: {model_name}")
    print("首次下载需要几分钟，请耐心等待...\n")

    model = SentenceTransformer(model_name)
    print(f"\n✅ 模型下载完成！")
    print(f"模型路径: {model._model_card_vars.get('model_name', model_name)}")


if __name__ == "__main__":
    main()
