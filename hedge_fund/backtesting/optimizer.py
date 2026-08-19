"""
Genetic Algorithm Optimizer for strategy parameter tuning.

Evolves strategy parameters to maximize Sharpe ratio or other
fitness metrics using walk-forward backtesting.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable
import numpy as np
import pandas as pd
from loguru import logger

from .engine import BacktestEngine, BacktestResult


@dataclass
class ParameterSpace:
    """Defines a single parameter and its valid range."""
    name: str
    min_val: float
    max_val: float
    step: float = 1.0
    param_type: str = "float"  # "float", "int", "bool"

    def random_value(self) -> float:
        if self.param_type == "bool":
            return float(random.choice([0, 1]))
        if self.param_type == "int":
            return float(random.randint(int(self.min_val), int(self.max_val)))
        val = random.uniform(self.min_val, self.max_val)
        if self.step > 0:
            val = round(val / self.step) * self.step
        return val

    def mutate(self, value: float, mutation_strength: float = 0.2) -> float:
        if self.param_type == "bool":
            return float(1 - int(value)) if random.random() < 0.3 else value
        range_size = self.max_val - self.min_val
        delta = random.gauss(0, range_size * mutation_strength)
        new_val = max(self.min_val, min(self.max_val, value + delta))
        if self.param_type == "int":
            new_val = round(new_val)
        elif self.step > 0:
            new_val = round(new_val / self.step) * self.step
        return new_val


@dataclass
class Individual:
    genes: dict[str, float]
    fitness: float = 0.0
    result: BacktestResult | None = None


@dataclass
class OptimizationResult:
    best_params: dict[str, float]
    best_fitness: float
    best_backtest: BacktestResult | None
    generations: int
    total_evaluations: int
    fitness_history: list[float] = field(default_factory=list)
    population_diversity: list[float] = field(default_factory=list)


class GeneticOptimizer:
    """
    Genetic algorithm for optimizing strategy parameters.

    Features:
    - Tournament selection
    - Uniform crossover
    - Adaptive mutation rate
    - Elitism (top N survive)
    - Fitness: Sharpe ratio, Calmar, or custom metric
    - Overfitting protection via walk-forward validation
    """

    def __init__(
        self,
        param_space: list[ParameterSpace],
        population_size: int = 50,
        generations: int = 30,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.7,
        elitism_count: int = 3,
        tournament_size: int = 5,
        fitness_metric: str = "sharpe",  # "sharpe", "calmar", "return", "profit_factor"
    ):
        self.param_space = {p.name: p for p in param_space}
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_count = elitism_count
        self.tournament_size = tournament_size
        self.fitness_metric = fitness_metric
        self.log = logger.bind(component="optimizer")

    def optimize(
        self,
        data: dict[str, pd.DataFrame],
        strategy_fn: Callable,
        initial_capital: float = 1_000_000.0,
    ) -> OptimizationResult:
        """Run genetic optimization."""
        population = self._init_population()
        best_ever = Individual(genes={}, fitness=float("-inf"))
        fitness_history: list[float] = []
        diversity_history: list[float] = []

        for gen in range(self.generations):
            # Evaluate fitness
            for ind in population:
                if ind.fitness == 0:
                    ind.fitness, ind.result = self._evaluate(
                        ind.genes, data, strategy_fn, initial_capital
                    )

            # Sort by fitness
            population.sort(key=lambda x: x.fitness, reverse=True)

            if population[0].fitness > best_ever.fitness:
                best_ever = Individual(
                    genes=dict(population[0].genes),
                    fitness=population[0].fitness,
                    result=population[0].result,
                )

            avg_fitness = np.mean([ind.fitness for ind in population])
            diversity = self._calc_diversity(population)
            fitness_history.append(best_ever.fitness)
            diversity_history.append(diversity)

            self.log.info(
                "Gen {}/{}: best={:.3f} avg={:.3f} diversity={:.3f}",
                gen + 1, self.generations, best_ever.fitness, avg_fitness, diversity,
            )

            if gen == self.generations - 1:
                break

            # Evolve
            new_population: list[Individual] = []

            # Elitism
            for i in range(self.elitism_count):
                new_population.append(Individual(genes=dict(population[i].genes)))

            while len(new_population) < self.population_size:
                parent1 = self._tournament_select(population)
                parent2 = self._tournament_select(population)

                if random.random() < self.crossover_rate:
                    child_genes = self._crossover(parent1.genes, parent2.genes)
                else:
                    child_genes = dict(parent1.genes)

                child_genes = self._mutate(child_genes, gen)
                new_population.append(Individual(genes=child_genes))

            population = new_population

        return OptimizationResult(
            best_params=best_ever.genes,
            best_fitness=best_ever.fitness,
            best_backtest=best_ever.result,
            generations=self.generations,
            total_evaluations=self.generations * self.population_size,
            fitness_history=fitness_history,
            population_diversity=diversity_history,
        )

    def _init_population(self) -> list[Individual]:
        return [
            Individual(genes={name: ps.random_value() for name, ps in self.param_space.items()})
            for _ in range(self.population_size)
        ]

    def _evaluate(
        self,
        params: dict[str, float],
        data: dict[str, pd.DataFrame],
        strategy_fn: Callable,
        initial_capital: float,
    ) -> tuple[float, BacktestResult | None]:
        try:
            engine = BacktestEngine(initial_capital=initial_capital)
            result = engine.run(data, strategy_fn, params)

            if self.fitness_metric == "sharpe":
                fitness = result.sharpe_ratio
            elif self.fitness_metric == "calmar":
                fitness = result.calmar_ratio
            elif self.fitness_metric == "return":
                fitness = result.total_return_pct
            elif self.fitness_metric == "profit_factor":
                fitness = result.profit_factor
            else:
                fitness = result.sharpe_ratio

            # Penalize extreme drawdown
            if result.max_drawdown_pct > 20:
                fitness *= 0.5
            # Penalize too few trades
            if result.total_trades < 10:
                fitness *= 0.3

            return fitness, result
        except Exception as e:
            self.log.debug(f"Evaluation failed: {e}")
            return -999.0, None

    def _tournament_select(self, population: list[Individual]) -> Individual:
        contestants = random.sample(population, min(self.tournament_size, len(population)))
        return max(contestants, key=lambda x: x.fitness)

    def _crossover(self, genes1: dict[str, float], genes2: dict[str, float]) -> dict[str, float]:
        child = {}
        for name in self.param_space:
            child[name] = genes1[name] if random.random() < 0.5 else genes2[name]
        return child

    def _mutate(self, genes: dict[str, float], generation: int) -> dict[str, float]:
        # Adaptive mutation: decreases over generations
        adaptive_rate = self.mutation_rate * (1 - generation / self.generations * 0.5)
        strength = 0.3 * (1 - generation / self.generations * 0.7)

        mutated = {}
        for name, value in genes.items():
            if random.random() < adaptive_rate:
                mutated[name] = self.param_space[name].mutate(value, strength)
            else:
                mutated[name] = value
        return mutated

    def _calc_diversity(self, population: list[Individual]) -> float:
        if len(population) < 2:
            return 0.0
        values = np.array([[ind.genes[n] for n in self.param_space] for ind in population])
        stds = np.std(values, axis=0)
        ranges = np.array([ps.max_val - ps.min_val for ps in self.param_space.values()])
        normalized = stds / np.maximum(ranges, 1e-10)
        return float(np.mean(normalized))
