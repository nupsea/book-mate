from collections import defaultdict


class SearchEvaluator:

    def __init__(self, chunks, searcher) -> None:
        self.chunks = chunks
        self.searcher = searcher
        self.results = []

    @staticmethod
    def hit_rate_at_k(res_ids, gold_id, k=5):
        return 1.0 if gold_id in res_ids[:k] else 0.0

    @staticmethod
    def mrr_at_k(res_ids, gold_id, k=5):
        for i, res_id in enumerate(res_ids[:k], start=1):
            if res_id == gold_id:
                return 1.0 / i
        return 0.0

    @staticmethod
    def calculate_metrics(results, k_values=[5, 7]):

        if not results:
            return {f"hit_rate_at_{k}": 0.0 for k in k_values} | {
                f"mrr_at_{k}": 0.0 for k in k_values
            }

        metrics = defaultdict(list)

        for result in results:
            res_ids = result.get("chunk_ids")
            gold_id = result.get("gold_id")

            for k in k_values:
                metrics[f"hit_rate_at_{k}"].append(
                    SearchEvaluator.hit_rate_at_k(res_ids, gold_id, k)
                )
                metrics[f"mrr_at_{k}"].append(
                    SearchEvaluator.mrr_at_k(res_ids, gold_id, k)
                )

        avg_metrics = {}
        for metric, values in metrics.items():
            avg_metrics[metric] = sum(values) / len(values) if values else 0.0

        avg_metrics["total_queries"] = len(results)

        return avg_metrics

    def evaluate(self, golden_data):
        results = []
        self.searcher.build_index(self.chunks)

        for item in golden_data:
            gold_id = item["gold_id"]
            query = item["query"]

            res = self.searcher.id_search(query)
            results.append({"gold_id": gold_id, "chunk_ids": res})
        metrics = SearchEvaluator.calculate_metrics(results)
        return metrics
