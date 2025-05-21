# Copyright (c) 2023, NVIDIA CORPORATION. All rights reserved.
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import torch
import numpy as np
from sympy import Symbol, Eq

import physicsnemo
from physicsnemo.sym.hydra import PhysicsNeMoConfig, instantiate_arch
from physicsnemo.sym.solver import Solver
from physicsnemo.sym.domain import Domain
from physicsnemo.sym.geometry.primitives_1d import Point1D
from physicsnemo.sym.geometry import Parameterization
from physicsnemo.sym.domain.constraint import (
    PointwiseBoundaryConstraint,
    PointwiseConstraint,
)
from physicsnemo.sym.domain.validator import PointwiseValidator
from physicsnemo.sym.domain.monitor import PointwiseMonitor
from physicsnemo.sym.key import Key
from physicsnemo.sym.node import Node

from spring_mass_ode import SpringMass


@physicsnemo.sym.main(config_path="conf", config_name="config_inverse")
def run(cfg: PhysicsNeMoConfig) -> None:
    # prepare data
    t_max = 10.0
    deltaT = 0.01
    t = np.arange(0, t_max, deltaT)
    t = np.expand_dims(t, axis=-1)

    invar_numpy = {"t": t}
    outvar_numpy = {
        "x1": (1 / 6) * np.cos(t)
        + (1 / 2) * np.cos(np.sqrt(3) * t)
        + (1 / 3) * np.cos(2 * t),
        "x2": (2 / 6) * np.cos(t)
        + (0 / 2) * np.cos(np.sqrt(3) * t)
        - (1 / 3) * np.cos(2 * t),
        "x3": (1 / 6) * np.cos(t)
        - (1 / 2) * np.cos(np.sqrt(3) * t)
        + (1 / 3) * np.cos(2 * t),
    }
    outvar_numpy.update({"ode_x1": np.full_like(invar_numpy["t"], 0)})
    outvar_numpy.update({"ode_x2": np.full_like(invar_numpy["t"], 0)})
    outvar_numpy.update({"ode_x3": np.full_like(invar_numpy["t"], 0)})

    # make list of nodes to unroll graph on
    sm = SpringMass(k=(2, 1, 1, "k4"), m=("m1", 1, 1))
    sm_net = instantiate_arch(
        input_keys=[Key("t")],
        output_keys=[Key("x1"), Key("x2"), Key("x3")],
        cfg=cfg.arch.fully_connected,
    )
    invert_net = instantiate_arch(
        input_keys=[Key("t")],
        output_keys=[Key("m1"), Key("k4")],
        cfg=cfg.arch.fully_connected,
    )

    nodes = (
        sm.make_nodes(
            detach_names=[
                "x1",
                "x1__t",
                "x1__t__t",
                "x2",
                "x2__t",
                "x2__t__t",
                "x3",
                "x3__t",
                "x3__t__t",
            ]
        )
        + [sm_net.make_node(name="spring_mass_network", jit=cfg.jit)]
        + [invert_net.make_node(name="invert_network", jit=cfg.jit)]
    )

    # add constraints to solver
    # make geometry
    geo = Point1D(0)
    t_symbol = Symbol("t")
    x = Symbol("x")
    time_range = {t_symbol: (0, t_max)}

    # make domain
    domain = Domain()

    # initial conditions
    IC = PointwiseBoundaryConstraint(
        nodes=nodes,
        geometry=geo,
        outvar={"x1": 1.0, "x2": 0, "x3": 0, "x1__t": 0, "x2__t": 0, "x3__t": 0},
        batch_size=cfg.batch_size.IC,
        lambda_weighting={
            "x1": 1.0,
            "x2": 1.0,
            "x3": 1.0,
            "x1__t": 1.0,
            "x2__t": 1.0,
            "x3__t": 1.0,
        },
        parameterization=Parameterization({t_symbol: 0}),
    )
    domain.add_constraint(IC, name="IC")

    # data and pdes
    data = PointwiseConstraint.from_numpy(
        nodes=nodes,
        invar=invar_numpy,
        outvar=outvar_numpy,
        batch_size=cfg.batch_size.data,
    )
    domain.add_constraint(data, name="Data")

    # add monitors
    monitor = PointwiseMonitor(
        invar_numpy,
        output_names=["m1"],
        metrics={"mean_m1": lambda var: torch.mean(var["m1"])},
        nodes=nodes,
    )
    domain.add_monitor(monitor)

    monitor = PointwiseMonitor(
        invar_numpy,
        output_names=["k4"],
        metrics={"mean_k4": lambda var: torch.mean(var["k4"])},
        nodes=nodes,
    )
    domain.add_monitor(monitor)

    # make solver
    slv = Solver(cfg, domain)

    # start solver
    slv.solve()


if __name__ == "__main__":
    run()
